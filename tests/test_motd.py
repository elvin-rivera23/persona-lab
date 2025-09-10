from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_motd_shape():
    r = client.get("/fun/motd")
    assert r.status_code == 200
    data = r.json()
    for key in ["logo", "quote", "tip", "build", "as_of"]:
        assert key in data
    assert data["build"]["service"] == "persona-lab"
    assert "version" in data["build"]
