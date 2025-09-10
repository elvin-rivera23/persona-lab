# tests/test_fun.py
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import EMOJI_MAP, app

client = TestClient(app)


def test_fun_greet_basic():
    r = client.get("/fun/greet?name=Kuya")
    assert r.status_code == 200
    data = r.json()
    assert data["message"].startswith("Hey Kuya")
    assert "tagline" in data and isinstance(data["tagline"], str)
    assert "as_of" in data


def test_fun_emoji_valid():
    for mood, emoji in EMOJI_MAP.items():
        r = client.get(f"/fun/emoji?mood={mood}")
        assert r.status_code == 200
        data = r.json()
        assert data["mood"] == mood
        assert data["emoji"] == emoji


def test_fun_emoji_invalid():
    r = client.get("/fun/emoji?mood=unknown")
    assert r.status_code == 400
    assert "Unsupported mood" in r.json()["detail"]


def test_fun_roll_defaults():
    r = client.get("/fun/roll")
    assert r.status_code == 200
    data = r.json()
    assert data["sides"] == 6
    assert data["count"] == 1
    assert isinstance(data["rolls"], list)
    assert len(data["rolls"]) == 1
    assert 1 <= data["rolls"][0] <= 6
    assert data["total"] == data["rolls"][0]


def test_fun_roll_params():
    r = client.get("/fun/roll?d=8&n=3")
    assert r.status_code == 200
    data = r.json()
    assert data["sides"] == 8
    assert data["count"] == 3
    assert len(data["rolls"]) == 3
    assert all(1 <= x <= 8 for x in data["rolls"])
    assert data["total"] == sum(data["rolls"])


def test_fun_teapot():
    r = client.get("/fun/teapot")
    assert r.status_code == 418
    body = r.json()
    assert body["code"] == 418
    assert "teapot" in body["message"].lower()
