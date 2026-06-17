"""Commercial edition gating.

A single codebase serves three editions. The OSS build (GitHub, BSL-licensed) runs
``oss`` and exposes core health + maintenance. The hosted SaaS (iceyard.dev) runs
``cloud`` / ``enterprise`` to unlock the paid value layer (advisors, FinOps, automation,
compliance/retention, DR). Gating is by ``ICEYARD_EDITION`` so the same code behaves
differently per license tier.
"""

from collections.abc import Callable
from enum import IntEnum

from fastapi import Depends, HTTPException, status

from iceyard_api.core.config import Settings, get_settings


class Edition(IntEnum):
    OSS = 0
    CLOUD = 1
    ENTERPRISE = 2


_EDITION_BY_NAME = {
    "oss": Edition.OSS,
    "cloud": Edition.CLOUD,
    "enterprise": Edition.ENTERPRISE,
}

# Feature flag -> minimum edition that unlocks it.
FEATURE_MIN_EDITION: dict[str, Edition] = {
    # Cloud / Team — autonomy, intelligence, FinOps, automation at fleet scale.
    "layout_whatif": Edition.CLOUD,
    "clustering_advisor": Edition.CLOUD,
    "format_advisor": Edition.CLOUD,
    "retention_simulation": Edition.CLOUD,
    "automation_policies": Edition.CLOUD,
    "wap_pipelines": Edition.CLOUD,
    "autonomous_optimization": Edition.CLOUD,
    "finops_ledger": Edition.CLOUD,
    # Enterprise — compliance, governance, DR (the budget-unlock tier).
    "data_retention": Edition.ENTERPRISE,
    "compliance_pack": Edition.ENTERPRISE,
    "disaster_recovery": Edition.ENTERPRISE,
    "sso_scim": Edition.ENTERPRISE,
}


def edition_from_settings(settings: Settings) -> Edition:
    return _EDITION_BY_NAME.get(settings.edition, Edition.OSS)


def has_feature(feature: str, edition: Edition) -> bool:
    return edition >= FEATURE_MIN_EDITION.get(feature, Edition.OSS)


def feature_matrix(edition: Edition) -> dict[str, bool]:
    return {name: edition >= minimum for name, minimum in FEATURE_MIN_EDITION.items()}


def require_feature(feature: str) -> Callable[..., None]:
    """FastAPI dependency that blocks a route unless the edition unlocks the feature."""

    def dependency(settings: Settings = Depends(get_settings)) -> None:
        edition = edition_from_settings(settings)
        if not has_feature(feature, edition):
            minimum = FEATURE_MIN_EDITION[feature]
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"'{feature}' requires the {minimum.name.lower()} edition; this "
                    f"deployment runs the {edition.name.lower()} edition. "
                    "See https://iceyard.dev for Cloud and Enterprise plans."
                ),
            )

    return dependency
