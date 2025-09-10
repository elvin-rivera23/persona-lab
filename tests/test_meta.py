from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_meta_has_keys():
    r = client.get("/__meta")
    assert r.status_code == 200
    body = r.json()
    for key in ["service", "version", "git", "build", "runtime", "endpoints"]:
        assert key in body
    assert "sha" in body["git"]
