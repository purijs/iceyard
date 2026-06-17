from fastapi.testclient import TestClient


def _first_table_id(client: TestClient, token: str) -> str:
    response = client.get("/api/v1/tables", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    return str(response.json()[0]["id"])


def test_layout_profile_returns_derived_metrics(client: TestClient, token: str) -> None:
    table_id = _first_table_id(client, token)
    response = client.get(
        f"/api/v1/tables/{table_id}/layout-profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["table_id"] == table_id
    assert body["derived"] is True
    assert 0.0 <= body["small_file_ratio"] <= 1.0
    assert body["avg_file_size_bytes"] >= 0
    assert body["delete_density"] >= 0
    assert any(dim["name"] == "Small-file ratio" for dim in body["dimensions"])
    assert len(body["clustering"]) > 0
    for candidate in body["clustering"]:
        assert candidate["clustering_depth"] >= 1.0


def test_layout_profile_unknown_table_is_404(client: TestClient, token: str) -> None:
    response = client.get(
        "/api/v1/tables/does-not-exist/layout-profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
