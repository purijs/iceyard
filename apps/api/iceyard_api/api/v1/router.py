from fastapi import APIRouter

from iceyard_api.approvals.router import router as approvals_router
from iceyard_api.audit.router import router as audit_router
from iceyard_api.auth.router import router as auth_router
from iceyard_api.connections.router import router as connections_router
from iceyard_api.health.router import router as health_router
from iceyard_api.iceberg.router import router as iceberg_router
from iceyard_api.jobs.router import router as jobs_router
from iceyard_api.layout.router import router as layout_router
from iceyard_api.operations.router import router as operations_router
from iceyard_api.policies.router import router as policies_router
from iceyard_api.rbac.router import router as rbac_router
from iceyard_api.tenants.router import router as tenants_router
from iceyard_api.tuning.router import router as tuning_router
from iceyard_api.users.router import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(tenants_router)
router.include_router(users_router)
router.include_router(rbac_router)
router.include_router(connections_router)
router.include_router(iceberg_router)
router.include_router(health_router)
router.include_router(operations_router)
router.include_router(layout_router)
router.include_router(tuning_router)
router.include_router(policies_router)
router.include_router(jobs_router)
router.include_router(approvals_router)
router.include_router(audit_router)
