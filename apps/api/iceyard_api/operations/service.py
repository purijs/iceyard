from string import Formatter

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.db.models import (
    ApprovalRequest,
    IcebergTable,
    Job,
    JobLog,
    JobRun,
    OperationRequest,
    RestorePoint,
    User,
)
from iceyard_api.operations.executor import OperationExecutor
from iceyard_api.operations.registry import OPERATION_BY_ID, OPERATIONS
from iceyard_api.operations.schemas import (
    GateResult,
    OperationDescriptor,
    OperationDryRunRead,
    OperationDryRunRequest,
    OperationExecuteRead,
)


def descriptor_by_id(operation_id: str) -> OperationDescriptor:
    descriptor = OPERATION_BY_ID.get(operation_id)
    if not descriptor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found.")
    return descriptor


def render_template(template: str, values: dict[str, object]) -> str:
    rendered_values = {
        key: values.get(key, "") for _, key, _, _ in Formatter().parse(template) if key
    }
    rendered_values.update(values)
    return template.format(**rendered_values)


class OperationService:
    def __init__(self, session: Session):
        self.session = session
        self.executor = OperationExecutor()

    def list_descriptors(self) -> list[OperationDescriptor]:
        return OPERATIONS

    def dry_run(self, *, payload: OperationDryRunRequest, actor: User) -> OperationDryRunRead:
        descriptor = descriptor_by_id(payload.operation_id)
        table = self._get_table(actor.workspace_id, payload.table_id)
        table_name = table.name if table else "catalog.table"
        params = self._params_with_defaults(descriptor, payload.params)
        compiled_command = render_template(
            descriptor.sql_template,
            {"table": table_name, **params},
        )
        gate_results = self._evaluate_gates(descriptor, params)
        metrics = self.executor.dry_run(
            descriptor=descriptor,
            compiled_command=compiled_command,
            table_name=table_name,
            params=params,
        )
        request = OperationRequest(
            workspace_id=actor.workspace_id,
            actor_id=actor.id,
            table_id=table.id if table else None,
            operation_id=descriptor.id,
            params=params,
            compiled_command=compiled_command,
            safety_class=descriptor.safety_class,
            dry_run_status="completed",
            gate_results=[gate.model_dump() for gate in gate_results],
        )
        self.session.add(request)
        self.session.flush()
        AuditService(self.session).record(
            action="operation.dry_run",
            resource_type="operation_request",
            resource_id=request.id,
            workspace_id=actor.workspace_id,
            actor_id=actor.id,
            after_state={
                "operation_id": descriptor.id,
                "table_id": request.table_id,
                "safety_class": descriptor.safety_class,
            },
        )
        self.session.commit()
        return OperationDryRunRead(
            id=request.id,
            operation_id=request.operation_id,
            table_id=request.table_id,
            compiled_command=request.compiled_command,
            safety_class=descriptor.safety_class,
            gate_results=gate_results,
            metrics=metrics,
            created_at=request.created_at,
        )

    def execute(
        self, *, dry_run_id: str, actor: User, confirmation: str | None
    ) -> OperationExecuteRead:
        request = self.session.scalar(
            select(OperationRequest).where(
                OperationRequest.id == dry_run_id,
                OperationRequest.workspace_id == actor.workspace_id,
            )
        )
        if not request:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dry-run not found.")
        descriptor = descriptor_by_id(request.operation_id)
        blocked = [gate for gate in request.gate_results if gate.get("status") == "blocked"]
        if blocked:
            return OperationExecuteRead(
                status="blocked",
                message="One or more safety gates are blocked.",
                job_id=None,
                approval_request_id=None,
            )
        if descriptor.approval_required:
            approval = ApprovalRequest(
                workspace_id=actor.workspace_id,
                operation_request_id=request.id,
                requested_by=actor.id,
                status="pending",
                reason="Operation requires approval before execution.",
                compiled_command_snapshot=request.compiled_command,
            )
            self.session.add(approval)
            self.session.flush()
            AuditService(self.session).record(
                action="approval.request",
                resource_type="approval_request",
                resource_id=approval.id,
                workspace_id=actor.workspace_id,
                actor_id=actor.id,
                after_state={"operation_id": descriptor.id},
            )
            self.session.commit()
            return OperationExecuteRead(
                status="requires_approval",
                approval_request_id=approval.id,
                job_id=None,
                message="Approval is required before this operation can run.",
            )
        if descriptor.safety_class == "DESTRUCTIVE" and confirmation != request.operation_id:
            return OperationExecuteRead(
                status="blocked",
                message="Confirmation did not match the operation identifier.",
                job_id=None,
                approval_request_id=None,
            )
        job = Job(
            workspace_id=actor.workspace_id,
            operation_request_id=request.id,
            kind="oneoff",
            status="queued",
            created_by=actor.id,
        )
        self.session.add(job)
        self.session.flush()
        restore_ref = None
        if descriptor.restore_point_required and request.table_id:
            restore_ref = f"restore-{job.id[:8]}"
            table = self.session.get(IcebergTable, request.table_id)
            snapshot_id = table.current_snapshot_id if table else "unknown"
            self.session.add(
                RestorePoint(
                    table_id=request.table_id,
                    operation_request_id=request.id,
                    name=restore_ref,
                    snapshot_id=snapshot_id or "unknown",
                    retention={"pinned": True},
                )
            )
        run = JobRun(
            job_id=job.id,
            status="queued",
            engine="mock",
            compiled_command=request.compiled_command,
            dry_run=False,
            pre_op_restore_ref=restore_ref,
            metrics={},
        )
        self.session.add(run)
        self.session.flush()
        self.session.add(
            JobLog(
                job_run_id=run.id,
                level="info",
                message=(
                    "Job queued. The executor is a local placeholder "
                    "until real engines are configured."
                ),
            )
        )
        AuditService(self.session).record(
            action="operation.execute.requested",
            resource_type="job",
            resource_id=job.id,
            workspace_id=actor.workspace_id,
            actor_id=actor.id,
            after_state={"operation_id": descriptor.id, "restore_point": restore_ref},
        )
        self.session.commit()
        return OperationExecuteRead(
            status="queued",
            job_id=job.id,
            approval_request_id=None,
            message="Job queued.",
        )

    def _get_table(self, workspace_id: str, table_id: str | None) -> IcebergTable | None:
        if not table_id:
            return None
        table = self.session.scalar(
            select(IcebergTable).where(
                IcebergTable.workspace_id == workspace_id, IcebergTable.id == table_id
            )
        )
        if not table:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found.")
        return table

    def _params_with_defaults(
        self, descriptor: OperationDescriptor, params: dict[str, object]
    ) -> dict[str, object]:
        values = dict(params)
        for param in descriptor.params:
            if param.name not in values and param.default is not None:
                values[param.name] = param.default
            if param.required and (param.name not in values or values[param.name] in {"", None}):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Missing required parameter: {param.name}",
                )
        return values

    def _evaluate_gates(
        self, descriptor: OperationDescriptor, params: dict[str, object]
    ) -> list[GateResult]:
        results: list[GateResult] = []
        for gate in descriptor.gates:
            status_value = "passed"
            detail = "Gate passed for this dry-run."
            if gate == "approval_required":
                status_value = "pending"
                detail = "Approval must be granted before execution."
            if gate == "retention_window_min_3_days":
                detail = (
                    "Retention window validation placeholder passed; "
                    "live storage checks are not enabled."
                )
            if gate == "path_authority_check":
                detail = "Path and authority validation placeholder passed."
            if gate == "reader_compatibility_check":
                detail = "Reader compatibility validation placeholder passed."
            results.append(
                GateResult(
                    id=gate, label=gate.replace("_", " "), status=status_value, detail=detail
                )
            )
        return results
