from fastapi.testclient import TestClient


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_policy(name: str = "prod-events-clustering") -> dict[str, object]:
    return {
        "name": name,
        "kind": "clustering",
        "selector": {"env": "dev", "namespace": "analytics", "name_glob": "analytics.*"},
        "trigger": {"kind": "schedule", "schedule": "0 3 * * *"},
        "action": {
            "op": "rewrite_data_files",
            "params": {"strategy": "sort", "sort_order": "zorder(user_id, occurred_at)"},
        },
        "guardrails": {"max_change_pct": 25, "approval": "first_run"},
    }


def test_policy_crud_and_match(client: TestClient, token: str) -> None:
    client.get("/api/v1/tables", headers=_auth(token))

    created = client.post("/api/v1/policies", json=_make_policy(), headers=_auth(token))
    assert created.status_code == 201, created.text
    policy_id = created.json()["id"]

    listed = client.get("/api/v1/policies", headers=_auth(token))
    assert listed.status_code == 200
    assert any(item["id"] == policy_id for item in listed.json())

    matched = client.get(f"/api/v1/policies/{policy_id}/match", headers=_auth(token))
    assert matched.status_code == 200, matched.text
    names = matched.json()["matched_table_names"]
    assert all(name.startswith("dev.analytics.") for name in names)
    assert names

    updated = client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"enabled": False},
        headers=_auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False

    deleted = client.delete(f"/api/v1/policies/{policy_id}", headers=_auth(token))
    assert deleted.status_code == 204


def test_policy_rejects_unknown_operation(client: TestClient, token: str) -> None:
    payload = _make_policy("bad-op")
    payload["action"] = {"op": "not_a_real_op", "params": {}}
    response = client.post("/api/v1/policies", json=payload, headers=_auth(token))
    assert response.status_code == 422


def test_policy_writes_audit_event(client: TestClient, token: str) -> None:
    client.post("/api/v1/policies", json=_make_policy("audited"), headers=_auth(token))
    audit = client.get("/api/v1/audit", headers=_auth(token))
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert "automation_policy.create" in actions
