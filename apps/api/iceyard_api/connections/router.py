from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.connections.schemas import (
    CatalogConnectionCreate,
    CatalogConnectionRead,
    ComputeBackendCreate,
    ComputeBackendRead,
    ConnectionTestResult,
    EnvironmentCreate,
    EnvironmentRead,
    ObjectStoreConnectionCreate,
    ObjectStoreConnectionRead,
)
from iceyard_api.connections.service import ConnectionService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session

router = APIRouter(tags=["connections"])


@router.post("/environments", response_model=EnvironmentRead, status_code=status.HTTP_201_CREATED)
def create_environment(
    payload: EnvironmentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> EnvironmentRead:
    service = ConnectionService(session)
    environment = service.create_environment(
        workspace_id=current_user.workspace_id, **payload.model_dump()
    )
    AuditService(session).record(
        action="environment.create",
        resource_type="environment",
        resource_id=environment.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": environment.name, "kind": environment.kind},
    )
    session.commit()
    return environment


@router.get("/environments", response_model=list[EnvironmentRead])
def list_environments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[EnvironmentRead]:
    return ConnectionService(session).list_environments(current_user.workspace_id)


@router.post(
    "/connections/catalogs",
    response_model=CatalogConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_connection(
    payload: CatalogConnectionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CatalogConnectionRead:
    service = ConnectionService(session)
    connection = service.create_catalog_connection(
        workspace_id=current_user.workspace_id, **payload.model_dump()
    )
    AuditService(session).record(
        action="connection.catalog.create",
        resource_type="catalog_connection",
        resource_id=connection.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": connection.name, "catalog_type": connection.catalog_type},
    )
    session.commit()
    return connection


@router.get("/connections/catalogs", response_model=list[CatalogConnectionRead])
def list_catalog_connections(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CatalogConnectionRead]:
    return ConnectionService(session).list_catalog_connections(current_user.workspace_id)


@router.post("/connections/catalogs/{connection_id}/test", response_model=ConnectionTestResult)
def test_catalog_connection(
    connection_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConnectionTestResult:
    service = ConnectionService(session)
    connection = service.get_catalog_connection(current_user.workspace_id, connection_id)
    if not connection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    result = service.test_catalog_connection(connection)
    AuditService(session).record(
        action="connection.catalog.test",
        resource_type="catalog_connection",
        resource_id=connection.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state=result,
    )
    session.commit()
    return ConnectionTestResult.model_validate(result)


@router.post(
    "/connections/object-stores",
    response_model=ObjectStoreConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_object_store_connection(
    payload: ObjectStoreConnectionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ObjectStoreConnectionRead:
    store = ConnectionService(session).create_object_store(
        workspace_id=current_user.workspace_id, **payload.model_dump()
    )
    AuditService(session).record(
        action="connection.object_store.create",
        resource_type="object_store_connection",
        resource_id=store.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": store.name, "store_type": store.store_type},
    )
    session.commit()
    return store


@router.post(
    "/connections/compute-backends",
    response_model=ComputeBackendRead,
    status_code=status.HTTP_201_CREATED,
)
def create_compute_backend(
    payload: ComputeBackendCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ComputeBackendRead:
    backend = ConnectionService(session).create_compute_backend(
        workspace_id=current_user.workspace_id, **payload.model_dump()
    )
    AuditService(session).record(
        action="connection.compute.create",
        resource_type="compute_backend",
        resource_id=backend.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": backend.name, "backend_type": backend.backend_type},
    )
    session.commit()
    return backend
