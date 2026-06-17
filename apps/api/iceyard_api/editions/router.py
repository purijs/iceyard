from fastapi import APIRouter, Depends
from pydantic import BaseModel

from iceyard_api.auth.dependencies import get_current_user
from iceyard_api.core.config import Settings, get_settings
from iceyard_api.db.models import User
from iceyard_api.editions.service import edition_from_settings, feature_matrix

router = APIRouter(prefix="/edition", tags=["edition"])


class EditionRead(BaseModel):
    edition: str
    features: dict[str, bool]


@router.get("", response_model=EditionRead)
def get_edition(
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> EditionRead:
    _ = current_user
    edition = edition_from_settings(settings)
    return EditionRead(edition=edition.name.lower(), features=feature_matrix(edition))
