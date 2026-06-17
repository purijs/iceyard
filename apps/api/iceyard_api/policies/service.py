import fnmatch

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from iceyard_api.core.time import utcnow
from iceyard_api.db.models import AutomationPolicy, Environment, IcebergTable
from iceyard_api.iceberg.service import IcebergIndexService
from iceyard_api.operations.registry import OPERATION_BY_ID
from iceyard_api.policies.schemas import (
    PolicyCreate,
    PolicyMatch,
    PolicyRead,
    PolicyUpdate,
)


class PolicyService:
    """S4 — CRUD + selector resolution for declarative automation policies."""

    def __init__(self, session: Session):
        self.session = session
        self.index = IcebergIndexService(session)

    def _to_read(self, policy: AutomationPolicy) -> PolicyRead:
        return PolicyRead(
            id=policy.id,
            name=policy.name,
            kind=policy.kind,
            enabled=policy.enabled,
            selector=policy.selector,
            trigger=policy.trigger,
            action=policy.action,
            guardrails=policy.guardrails,
            alerting=policy.alerting,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    def _validate_action_op(self, op_id: str) -> None:
        if op_id not in OPERATION_BY_ID:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown operation in policy action: {op_id}",
            )

    def list_policies(self, workspace_id: str) -> list[PolicyRead]:
        rows = self.session.scalars(
            select(AutomationPolicy)
            .where(AutomationPolicy.workspace_id == workspace_id)
            .order_by(AutomationPolicy.name)
        )
        return [self._to_read(row) for row in rows]

    def get_policy(self, workspace_id: str, policy_id: str) -> AutomationPolicy:
        policy = self.session.scalar(
            select(AutomationPolicy).where(
                AutomationPolicy.workspace_id == workspace_id,
                AutomationPolicy.id == policy_id,
            )
        )
        if not policy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found.")
        return policy

    def create_policy(
        self, workspace_id: str, payload: PolicyCreate, created_by: str | None
    ) -> PolicyRead:
        self._validate_action_op(payload.action.op)
        existing = self.session.scalar(
            select(AutomationPolicy).where(
                AutomationPolicy.workspace_id == workspace_id,
                AutomationPolicy.name == payload.name,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A policy with this name already exists.",
            )
        policy = AutomationPolicy(
            workspace_id=workspace_id,
            name=payload.name,
            kind=payload.kind,
            enabled=payload.enabled,
            selector=payload.selector.model_dump(),
            trigger=payload.trigger.model_dump(),
            action=payload.action.model_dump(),
            guardrails=payload.guardrails.model_dump(),
            alerting=payload.alerting.model_dump(),
            created_by=created_by,
        )
        self.session.add(policy)
        self.session.flush()
        return self._to_read(policy)

    def update_policy(
        self, workspace_id: str, policy_id: str, payload: PolicyUpdate
    ) -> PolicyRead:
        policy = self.get_policy(workspace_id, policy_id)
        if payload.action is not None:
            self._validate_action_op(payload.action.op)
            policy.action = payload.action.model_dump()
        if payload.enabled is not None:
            policy.enabled = payload.enabled
        if payload.selector is not None:
            policy.selector = payload.selector.model_dump()
        if payload.trigger is not None:
            policy.trigger = payload.trigger.model_dump()
        if payload.guardrails is not None:
            policy.guardrails = payload.guardrails.model_dump()
        if payload.alerting is not None:
            policy.alerting = payload.alerting.model_dump()
        policy.updated_at = utcnow()
        self.session.flush()
        return self._to_read(policy)

    def delete_policy(self, workspace_id: str, policy_id: str) -> None:
        policy = self.get_policy(workspace_id, policy_id)
        self.session.delete(policy)
        self.session.flush()

    def match(self, workspace_id: str, policy_id: str) -> PolicyMatch:
        policy = self.get_policy(workspace_id, policy_id)
        tables = self._resolve_selector(workspace_id, policy.selector or {})
        return PolicyMatch(
            policy_id=policy.id,
            policy_name=policy.name,
            matched_table_ids=[table.id for table in tables],
            matched_table_names=[f"{table.environment.name}.{table.name}" for table in tables],
        )

    def _resolve_selector(
        self, workspace_id: str, selector: dict[str, object]
    ) -> list[IcebergTable]:
        tables = self.index.list_tables(workspace_id)
        env_name = selector.get("env")
        namespace = selector.get("namespace")
        name_glob = selector.get("name_glob")
        raw_min_size = selector.get("min_size_gb")
        min_size_bytes = (
            float(raw_min_size) * 1_000_000_000
            if isinstance(raw_min_size, int | float)
            else None
        )

        env_id: str | None = None
        if env_name:
            environment = self.session.scalar(
                select(Environment).where(
                    Environment.workspace_id == workspace_id,
                    Environment.name == env_name,
                )
            )
            env_id = environment.id if environment else "__none__"

        matched: list[IcebergTable] = []
        for table in tables:
            if env_id and table.environment_id != env_id:
                continue
            if namespace and not table.name.startswith(f"{namespace}."):
                continue
            if name_glob and not fnmatch.fnmatch(table.name, str(name_glob)):
                continue
            if (
                min_size_bytes is not None
                and table.metrics
                and table.metrics.data_size_bytes < min_size_bytes
            ):
                continue
            matched.append(table)
        return matched
