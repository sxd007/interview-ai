import pytest


def test_health_check(client):
    response = client.get("/api/interviews/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data


def test_list_interviews_empty(client):
    response = client.get("/api/interviews")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["interviews"] == []


def test_list_interviews_pagination(client, db_session):
    response = client.get("/api/interviews?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "interviews" in data


def test_get_interview_not_found(client):
    response = client.get("/api/interviews/non-existent-id")
    assert response.status_code == 404


def test_delete_interview_not_found(client):
    response = client.delete("/api/interviews/non-existent-id")
    assert response.status_code == 404
