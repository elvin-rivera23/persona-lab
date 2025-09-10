# tests/test_playground.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_playground_serves_html():
    r = client.get("/fun/playground")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
    # Key markers present:
    for marker in ["Persona Lab — Playground", "brew-418", "/fun/motd", "/fun/teapot"]:
        assert marker in r.text
