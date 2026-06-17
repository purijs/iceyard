from fastapi.testclient import TestClient


def test_default_admin_login_password_change_and_current_user(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["username"] == "admin"

    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": "admin", "new_password": "admin2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert changed.status_code == 200, changed.text

    old_login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin2"},
    )
    assert new_login.status_code == 200


def test_roles_are_seeded(client: TestClient, token: str) -> None:
    response = client.get("/api/v1/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    names = {role["name"] for role in response.json()}
    assert {"platform_admin", "workspace_admin", "maintainer", "analyst", "viewer"} <= names


def test_workspace_user_and_role_management(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}

    workspace = client.get("/api/v1/workspaces/current", headers=headers)
    assert workspace.status_code == 200
    assert workspace.json()["name"] == "default"

    renamed = client.patch(
        "/api/v1/workspaces/current", headers=headers, json={"name": "Iceyard Ops"}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Iceyard Ops"

    role = client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "name": "support",
            "permissions": [
                {"action": "tables.read", "resource_selector": {"scope": "*"}},
                {"action": "jobs.read", "resource_selector": {"scope": "*"}},
            ],
        },
    )
    assert role.status_code == 201, role.text
    role_id = role.json()["id"]

    user = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "support",
            "password": "support",
            "role_ids": [role_id],
        },
    )
    assert user.status_code == 201, user.text
    user_body = user.json()
    assert user_body["username"] == "support"
    assert user_body["roles"][0]["name"] == "support"

    replacement = client.put(
        f"/api/v1/roles/users/{user_body['id']}", headers=headers, json={"role_ids": []}
    )
    assert replacement.status_code == 200, replacement.text
    assert replacement.json()["role_ids"] == []

    deactivated = client.delete(f"/api/v1/users/{user_body['id']}", headers=headers)
    assert deactivated.status_code == 204, deactivated.text

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "support", "password": "support"},
    )
    assert login.status_code == 401

    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert {"workspaces.update", "roles.create", "users.create", "users.deactivate"} <= actions
