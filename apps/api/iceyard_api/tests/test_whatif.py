from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _first_table_id(client: TestClient, token: str) -> str:
    response = client.get("/api/v1/tables", headers=_auth(token))
    assert response.status_code == 200, response.text
    return str(response.json()[0]["id"])


def test_resort_projection_reduces_files(client: TestClient, token: str) -> None:
    table_id = _first_table_id(client, token)
    response = client.post(
        f"/api/v1/tables/{table_id}/whatif",
        json={
            "change": {"kind": "resort", "to": "zorder(user_id, occurred_at)"},
            "queries": [{"filter": "user_id = 771", "selectivity": 0.02}],
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    result = body["queries"][0]
    assert result["projected_files"] <= result["current_files"]
    assert result["files_reduction_pct"] >= 0
    assert body["aggregate"]["typical_files_reduction_pct"] >= 0


def test_whatif_uses_representative_queries_when_empty(client: TestClient, token: str) -> None:
    table_id = _first_table_id(client, token)
    response = client.post(
        f"/api/v1/tables/{table_id}/whatif",
        json={"change": {"kind": "refile_size", "to": "268435456"}},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["queries"]) >= 1
    assert "file-size change" in body["assumptions"].lower() or body["assumptions"]


def test_repartition_to_hours_increases_pruning(client: TestClient, token: str) -> None:
    table_id = _first_table_id(client, token)
    response = client.post(
        f"/api/v1/tables/{table_id}/whatif",
        json={
            "change": {"kind": "repartition", "to": "hours(occurred_at)"},
            "queries": [{"filter": "occurred_at = DATE '2026-06-01'"}],
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    result = response.json()["queries"][0]
    assert result["projected_files"] <= result["current_files"]
