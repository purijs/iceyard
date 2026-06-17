import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ICEYARD_DATABASE_URL", "sqlite:///./test_iceyard.db")
os.environ.setdefault("ICEYARD_ENVIRONMENT", "test")
# Tests exercise the full feature surface; gating itself is covered in test_editions.
os.environ.setdefault("ICEYARD_EDITION", "enterprise")

from iceyard_api.db.base import Base
from iceyard_api.db.session import engine
from iceyard_api.main import app


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def token(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])
