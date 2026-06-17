from fastapi.testclient import TestClient


def test_bootstrap_login_and_current_user(client: TestClient) -> None:
    bootstrap = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "workspace_name": "Iceyard",
            "email": "admin@example.com",
            "password": "change-this-password",
            "display_name": "Platform Admin",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    token = bootstrap.json()["token"]["access_token"]

    duplicate = client.post(
        "/api/v1/auth/bootstrap",
        json={
            "workspace_name": "Other",
            "email": "other@example.com",
            "password": "change-this-password",
            "display_name": "Other Admin",
        },
    )
    assert duplicate.status_code == 409

    current = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["email"] == "admin@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-this-password"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_roles_are_seeded(client: TestClient, token: str) -> None:
    response = client.get("/api/v1/roles", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    names = {role["name"] for role in response.json()}
    assert {"platform_admin", "workspace_admin", "maintainer", "analyst", "viewer"} <= names


def test_workspace_user_and_role_management(client: TestClient, token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}

    workspace = client.get("/api/v1/workspaces/current", headers=headers)
    assert workspace.status_code == 200
    assert workspace.json()["name"] == "Iceyard"

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
            "email": "support@example.com",
            "display_name": "Support",
            "password": "support-password",
            "role_ids": [role_id],
        },
    )
    assert user.status_code == 201, user.text
    user_body = user.json()
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
        json={"email": "support@example.com", "password": "support-password"},
    )
    assert login.status_code == 401

    audit = client.get("/api/v1/audit", headers=headers)
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert {"workspaces.update", "roles.create", "users.create", "users.deactivate"} <= actions
