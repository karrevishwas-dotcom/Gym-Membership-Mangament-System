import os
import tempfile
import pytest

os.environ["SECRET_KEY"] = "test-secret"

from app import app

@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app as gymapp
    db = tmp_path / "test.db"
    monkeypatch.setattr(gymapp, "DATABASE", str(db))
    app.config.update(TESTING=True)
    with app.test_client() as client:
        client.post("/login", data={"username": "admin", "password": "admin123"})
        yield client

def test_pages_load(client):
    for path in ["/", "/members", "/attendance", "/membership-plans", "/memberships",
                 "/payments", "/trainers", "/users", "/reports"]:
        response = client.get(path)
        assert response.status_code == 200

def test_attendance_crud(client):
    response = client.post("/members/add", data={
        "name": "Test Member", "phone": "9876543210",
        "email": "test@example.com", "age": "25", "gender": "Male",
        "join_date": "2026-10-03"
    })
    assert response.status_code == 302

    response = client.post("/attendance/add", data={
        "member_id": "1", "attendance_date": "2026-10-03", "status": "Present"
    })
    assert response.status_code == 302

    response = client.get("/attendance")
    assert response.status_code == 200
    assert b"Test Member" in response.data
    assert b"Present" in response.data
    assert b"Database Error" not in response.data

    response = client.post("/attendance/add", data={
        "member_id": "1", "attendance_date": "2026-10-03", "status": "Absent"
    })
    assert response.status_code == 302

    response = client.get("/attendance")
    assert b"Absent" in response.data
