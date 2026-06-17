from fastapi import APIRouter, Depends

from iceyard_api.advisor.router import router as advisor_router
from iceyard_api.approvals.router import router as approvals_router
from iceyard_api.audit.router import router as audit_router
from iceyard_api.auth.router import router as auth_router
from iceyard_api.connections.router import router as connections_router
from iceyard_api.editions.router import router as edition_router
from iceyard_api.editions.service import require_feature
from iceyard_api.health.router import router as health_router
from iceyard_api.iceberg.router import router as iceberg_router
from iceyard_api.jobs.router import router as jobs_router
from iceyard_api.layout.router import router as layout_router
from iceyard_api.operations.router import router as operations_router
from iceyard_api.policies.router import router as policies_router
from iceyard_api.rbac.router import router as rbac_router
from iceyard_api.retention.router import router as retention_router
from iceyard_api.tenants.router import router as tenants_router
from iceyard_api.tuning.router import router as tuning_router
from iceyard_api.users.router import router as users_router
from iceyard_api.wap.router import router as wap_router

router = APIRouter(prefix="/api/v1")

# --- OSS core (BSL, free) -------------------------------------------------------------
router.include_router(auth_router)
router.include_router(edition_router)
router.include_router(tenants_router)
router.include_router(users_router)
router.include_router(rbac_router)
router.include_router(connections_router)
router.include_router(iceberg_router)
router.include_router(health_router)
router.include_router(operations_router)
router.include_router(jobs_router)
router.include_router(approvals_router)
router.include_router(audit_router)
# layout-profile is OSS; the what-if route inside is gated per-route (Cloud).
router.include_router(layout_router)
# retention has a Cloud route (simulate) and an Enterprise route (cleanup), gated per-route.
router.include_router(retention_router)

# --- Cloud / Enterprise paid features (gated by edition) ------------------------------
router.include_router(
    tuning_router, dependencies=[Depends(require_feature("format_advisor"))]
)
router.include_router(
    advisor_router, dependencies=[Depends(require_feature("clustering_advisor"))]
)
router.include_router(
    wap_router, dependencies=[Depends(require_feature("wap_pipelines"))]
)
router.include_router(
    policies_router, dependencies=[Depends(require_feature("automation_policies"))]
)
