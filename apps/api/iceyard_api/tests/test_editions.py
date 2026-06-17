from fastapi.testclient import TestClient

from iceyard_api.editions.service import (
    Edition,
    edition_from_settings,
    feature_matrix,
    has_feature,
)


class _FakeSettings:
    def __init__(self, edition: str) -> None:
        self.edition = edition


def test_oss_edition_locks_paid_features() -> None:
    oss = edition_from_settings(_FakeSettings("oss"))
    assert oss is Edition.OSS
    assert has_feature("clustering_advisor", oss) is False
    assert has_feature("data_retention", oss) is False
    matrix = feature_matrix(oss)
    assert matrix["clustering_advisor"] is False
    assert matrix["data_retention"] is False


def test_cloud_unlocks_cloud_not_enterprise() -> None:
    cloud = edition_from_settings(_FakeSettings("cloud"))
    assert has_feature("clustering_advisor", cloud) is True
    assert has_feature("layout_whatif", cloud) is True
    assert has_feature("data_retention", cloud) is False  # enterprise-only


def test_enterprise_unlocks_everything() -> None:
    enterprise = edition_from_settings(_FakeSettings("enterprise"))
    assert all(feature_matrix(enterprise).values())


def test_edition_endpoint_reports_features(client: TestClient, token: str) -> None:
    response = client.get(
        "/api/v1/edition", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["edition"] == "enterprise"  # set in conftest
    assert body["features"]["clustering_advisor"] is True
    assert body["features"]["data_retention"] is True
