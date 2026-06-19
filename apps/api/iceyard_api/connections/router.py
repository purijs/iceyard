from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from iceyard_api.audit.service import AuditService
from iceyard_api.connections.schemas import (
    CatalogConnectionCreate,
    CatalogConnectionRead,
    CatalogConnectionUpdate,
    ComputeBackendCreate,
    ComputeBackendRead,
    ComputeBackendUpdate,
    ConnectionTestResult,
    EnvironmentCreate,
    EnvironmentRead,
    EnvironmentUpdate,
    ObjectStoreConnectionCreate,
    ObjectStoreConnectionRead,
    ObjectStoreConnectionUpdate,
    SecretReferenceCreate,
    SecretReferenceRead,
    SecretReferenceUpdate,
)
from iceyard_api.connections.service import ConnectionService
from iceyard_api.db.models import User
from iceyard_api.db.session import get_session
from iceyard_api.rbac.dependencies import require_permission

router = APIRouter(tags=["connections"])


@router.post("/environments", response_model=EnvironmentRead, status_code=status.HTTP_201_CREATED)
def create_environment(
    payload: EnvironmentCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
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
    current_user: User = Depends(require_permission("connections.read")),
) -> list[EnvironmentRead]:
    return ConnectionService(session).list_environments(current_user.workspace_id)


@router.get("/environments/{environment_id}", response_model=EnvironmentRead)
def get_environment(
    environment_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> EnvironmentRead:
    return ConnectionService(session).get_environment(current_user.workspace_id, environment_id)


@router.patch("/environments/{environment_id}", response_model=EnvironmentRead)
def update_environment(
    environment_id: str,
    payload: EnvironmentUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> EnvironmentRead:
    service = ConnectionService(session)
    environment = service.get_environment(current_user.workspace_id, environment_id)
    before_state = {
        "name": environment.name,
        "kind": environment.kind,
        "region": environment.region,
    }
    environment = service.update_environment(
        current_user.workspace_id,
        environment_id,
        payload.model_dump(exclude_unset=True),
    )
    AuditService(session).record(
        action="environment.update",
        resource_type="environment",
        resource_id=environment.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={
            "name": environment.name,
            "kind": environment.kind,
            "region": environment.region,
        },
    )
    session.commit()
    return environment


@router.delete("/environments/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_environment(
    environment_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> Response:
    service = ConnectionService(session)
    environment = service.get_environment(current_user.workspace_id, environment_id)
    service.delete_environment(current_user.workspace_id, environment_id)
    AuditService(session).record(
        action="environment.delete",
        resource_type="environment",
        resource_id=environment_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state={"name": environment.name, "kind": environment.kind},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/connections/catalogs",
    response_model=CatalogConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_connection(
    payload: CatalogConnectionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
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
    current_user: User = Depends(require_permission("connections.read")),
) -> list[CatalogConnectionRead]:
    return ConnectionService(session).list_catalog_connections(current_user.workspace_id)


@router.get("/connections/catalogs/{connection_id}", response_model=CatalogConnectionRead)
def get_catalog_connection(
    connection_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> CatalogConnectionRead:
    return ConnectionService(session).get_catalog_connection(
        current_user.workspace_id, connection_id
    )


@router.patch("/connections/catalogs/{connection_id}", response_model=CatalogConnectionRead)
def update_catalog_connection(
    connection_id: str,
    payload: CatalogConnectionUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> CatalogConnectionRead:
    service = ConnectionService(session)
    connection = service.get_catalog_connection(current_user.workspace_id, connection_id)
    before_state = {
        "name": connection.name,
        "catalog_type": connection.catalog_type,
        "is_enabled": connection.is_enabled,
    }
    connection = service.update_catalog_connection(
        current_user.workspace_id,
        connection_id,
        payload.model_dump(exclude_unset=True),
    )
    AuditService(session).record(
        action="connection.catalog.update",
        resource_type="catalog_connection",
        resource_id=connection.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={
            "name": connection.name,
            "catalog_type": connection.catalog_type,
            "is_enabled": connection.is_enabled,
        },
    )
    session.commit()
    return connection


@router.delete("/connections/catalogs/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_catalog_connection(
    connection_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> Response:
    service = ConnectionService(session)
    connection = service.get_catalog_connection(current_user.workspace_id, connection_id)
    service.delete_catalog_connection(current_user.workspace_id, connection_id)
    AuditService(session).record(
        action="connection.catalog.delete",
        resource_type="catalog_connection",
        resource_id=connection_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state={"name": connection.name, "catalog_type": connection.catalog_type},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/connections/catalogs/{connection_id}/test", response_model=ConnectionTestResult)
def test_catalog_connection(
    connection_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> ConnectionTestResult:
    service = ConnectionService(session)
    connection = service.get_catalog_connection(current_user.workspace_id, connection_id)
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
    current_user: User = Depends(require_permission("connections.manage")),
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


@router.get("/connections/object-stores", response_model=list[ObjectStoreConnectionRead])
def list_object_store_connections(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> list[ObjectStoreConnectionRead]:
    return ConnectionService(session).list_object_stores(current_user.workspace_id)


@router.get("/connections/object-stores/{store_id}", response_model=ObjectStoreConnectionRead)
def get_object_store_connection(
    store_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> ObjectStoreConnectionRead:
    return ConnectionService(session).get_object_store(current_user.workspace_id, store_id)


@router.patch("/connections/object-stores/{store_id}", response_model=ObjectStoreConnectionRead)
def update_object_store_connection(
    store_id: str,
    payload: ObjectStoreConnectionUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> ObjectStoreConnectionRead:
    service = ConnectionService(session)
    store = service.get_object_store(current_user.workspace_id, store_id)
    before_state = {"name": store.name, "store_type": store.store_type}
    store = service.update_object_store(
        current_user.workspace_id,
        store_id,
        payload.model_dump(exclude_unset=True),
    )
    AuditService(session).record(
        action="connection.object_store.update",
        resource_type="object_store_connection",
        resource_id=store.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"name": store.name, "store_type": store.store_type},
    )
    session.commit()
    return store


@router.delete("/connections/object-stores/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_object_store_connection(
    store_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> Response:
    service = ConnectionService(session)
    store = service.get_object_store(current_user.workspace_id, store_id)
    service.delete_object_store(current_user.workspace_id, store_id)
    AuditService(session).record(
        action="connection.object_store.delete",
        resource_type="object_store_connection",
        resource_id=store_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state={"name": store.name, "store_type": store.store_type},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/connections/object-stores/{store_id}/test", response_model=ConnectionTestResult)
def test_object_store_connection(
    store_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> ConnectionTestResult:
    service = ConnectionService(session)
    store = service.get_object_store(current_user.workspace_id, store_id)
    result = service.test_object_store(store)
    AuditService(session).record(
        action="connection.object_store.test",
        resource_type="object_store_connection",
        resource_id=store.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state=result,
    )
    session.commit()
    return ConnectionTestResult.model_validate(result)


@router.post(
    "/connections/compute-backends",
    response_model=ComputeBackendRead,
    status_code=status.HTTP_201_CREATED,
)
def create_compute_backend(
    payload: ComputeBackendCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
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


@router.get("/connections/compute-backends", response_model=list[ComputeBackendRead])
def list_compute_backends(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> list[ComputeBackendRead]:
    return ConnectionService(session).list_compute_backends(current_user.workspace_id)


@router.get("/connections/compute-backends/{backend_id}", response_model=ComputeBackendRead)
def get_compute_backend(
    backend_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> ComputeBackendRead:
    return ConnectionService(session).get_compute_backend(current_user.workspace_id, backend_id)


@router.patch("/connections/compute-backends/{backend_id}", response_model=ComputeBackendRead)
def update_compute_backend(
    backend_id: str,
    payload: ComputeBackendUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> ComputeBackendRead:
    service = ConnectionService(session)
    backend = service.get_compute_backend(current_user.workspace_id, backend_id)
    before_state = {
        "name": backend.name,
        "backend_type": backend.backend_type,
        "is_enabled": backend.is_enabled,
    }
    backend = service.update_compute_backend(
        current_user.workspace_id,
        backend_id,
        payload.model_dump(exclude_unset=True),
    )
    AuditService(session).record(
        action="connection.compute.update",
        resource_type="compute_backend",
        resource_id=backend.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={
            "name": backend.name,
            "backend_type": backend.backend_type,
            "is_enabled": backend.is_enabled,
        },
    )
    session.commit()
    return backend


@router.delete("/connections/compute-backends/{backend_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compute_backend(
    backend_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> Response:
    service = ConnectionService(session)
    backend = service.get_compute_backend(current_user.workspace_id, backend_id)
    service.delete_compute_backend(current_user.workspace_id, backend_id)
    AuditService(session).record(
        action="connection.compute.delete",
        resource_type="compute_backend",
        resource_id=backend_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state={"name": backend.name, "backend_type": backend.backend_type},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/secrets/references",
    response_model=SecretReferenceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_secret_reference(
    payload: SecretReferenceCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> SecretReferenceRead:
    secret = ConnectionService(session).create_secret_reference(
        workspace_id=current_user.workspace_id, **payload.model_dump()
    )
    AuditService(session).record(
        action="secret_reference.create",
        resource_type="secret_reference",
        resource_id=secret.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        after_state={"name": secret.name, "provider": secret.provider, "has_reference": True},
    )
    session.commit()
    return SecretReferenceRead.model_validate(secret)


@router.get("/secrets/references", response_model=list[SecretReferenceRead])
def list_secret_references(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.read")),
) -> list[SecretReferenceRead]:
    return ConnectionService(session).list_secret_references(current_user.workspace_id)


@router.patch("/secrets/references/{secret_id}", response_model=SecretReferenceRead)
def update_secret_reference(
    secret_id: str,
    payload: SecretReferenceUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> SecretReferenceRead:
    service = ConnectionService(session)
    secret = service.get_secret_reference(current_user.workspace_id, secret_id)
    before_state = {"name": secret.name, "provider": secret.provider, "has_reference": True}
    secret = service.update_secret_reference(
        current_user.workspace_id,
        secret_id,
        payload.model_dump(exclude_unset=True),
    )
    AuditService(session).record(
        action="secret_reference.update",
        resource_type="secret_reference",
        resource_id=secret.id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state=before_state,
        after_state={"name": secret.name, "provider": secret.provider, "has_reference": True},
    )
    session.commit()
    return SecretReferenceRead.model_validate(secret)


@router.delete("/secrets/references/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret_reference(
    secret_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission("connections.manage")),
) -> Response:
    service = ConnectionService(session)
    secret = service.get_secret_reference(current_user.workspace_id, secret_id)
    service.delete_secret_reference(current_user.workspace_id, secret_id)
    AuditService(session).record(
        action="secret_reference.delete",
        resource_type="secret_reference",
        resource_id=secret_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        before_state={"name": secret.name, "provider": secret.provider, "has_reference": True},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
