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
