from fastapi.testclient import TestClient

from iceyard_api.core.config import Settings


def test_local_mode_allows_private_lan_origin(client: TestClient) -> None:
    origin = "http://192.168.33.104:3000"
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == origin


def test_explicit_regex_overrides_local_default() -> None:
    settings = Settings(
        environment="production", cors_origin_regex=r"^https://app\.example\.com$"
    )
    assert settings.effective_cors_origin_regex() == r"^https://app\.example\.com$"


def test_production_without_regex_has_no_lan_default() -> None:
    settings = Settings(environment="production")
    assert settings.effective_cors_origin_regex() is None


def test_local_mode_default_matches_lan_and_localhost() -> None:
    import re

    pattern = re.compile(Settings(environment="test").effective_cors_origin_regex() or "")
    assert pattern.match("http://localhost:3000")
    assert pattern.match("http://192.168.33.104:3000")
    assert pattern.match("http://10.0.0.5:3000")
    assert not pattern.match("http://evil.example.com")
