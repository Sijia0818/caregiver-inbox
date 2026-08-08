import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["CAREPORTAL_DB_PATH"] = str(Path(__file__).parent / "test_careportal.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import PATIENT_ID, app, init_db  # noqa: E402


@pytest.fixture(autouse=True)
def reset_db():
    init_db(reset=True)
    yield
    db_file = Path(os.environ["CAREPORTAL_DB_PATH"])
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def client():
    return TestClient(app)


HEADERS = {"X-Caregiver-Id": "CG-001"}


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["isSynthetic"] is True


def test_appointment_retrieval(client):
    response = client.get(f"/api/patients/{PATIENT_ID}/appointments", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["isSynthetic"] is True
    assert body["appointments"][0]["id"] == "APT-001"


def test_update_retrieval_since(client):
    response = client.get(f"/api/patients/{PATIENT_ID}/updates?since=2026-08-07T08:00:00+08:00", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["updates"][0]["id"] == "UPDATE-001"


def test_successful_rescheduling_creates_notification_and_audit(client):
    response = client.post("/api/appointments/APT-001/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS)
    assert response.status_code == 200
    appointment = response.json()["appointment"]
    assert appointment["datetime"] == "2026-08-18T09:30:00+08:00"
    assert appointment["previousDatetime"] == "2026-08-15T10:30:00+08:00"

    notifications = client.get(f"/api/patients/{PATIENT_ID}/notifications", headers=HEADERS).json()["notifications"]
    assert any(item["title"] == "Reschedule confirmed" for item in notifications)

    audit = client.get("/api/audit-log").json()["entries"]
    assert any(item["action"] == "appointment_reschedule" and item["outcome"] == "success" for item in audit)


def test_booking_appointment_creates_notification_update_and_audit(client):
    response = client.post(
        f"/api/patients/{PATIENT_ID}/appointments",
        json={"facility": "CarePortal General Hospital", "department": "Geriatric Medicine", "date": "2026-09-01"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    appointment = response.json()["appointment"]
    assert appointment["facility"] == "CarePortal General Hospital"
    assert appointment["department"] == "Geriatric Medicine"
    assert appointment["datetime"] == "2026-09-01T09:00:00+08:00"
    assert appointment["status"] == "confirmed"

    appointments = client.get(f"/api/patients/{PATIENT_ID}/appointments", headers=HEADERS).json()["appointments"]
    assert any(item["id"] == appointment["id"] for item in appointments)

    notifications = client.get(f"/api/patients/{PATIENT_ID}/notifications", headers=HEADERS).json()["notifications"]
    assert any(item["title"] == "Appointment booked" and item["relatedResourceId"] == appointment["id"] for item in notifications)

    updates = client.get(f"/api/patients/{PATIENT_ID}/updates", headers=HEADERS).json()["updates"]
    assert any(item["type"] == "appointment_booked" and item["resourceId"] == appointment["id"] for item in updates)

    audit = client.get("/api/audit-log").json()["entries"]
    assert any(item["action"] == "appointment_book" and item["outcome"] == "success" for item in audit)


def test_cancel_non_cardiology_appointment(client):
    response = client.post("/api/appointments/APT-002/cancel", headers=HEADERS)
    assert response.status_code == 200
    appointment = response.json()["appointment"]
    assert appointment["department"] == "Physiotherapy"
    assert appointment["status"] == "cancelled"

    notifications = client.get(f"/api/patients/{PATIENT_ID}/notifications", headers=HEADERS).json()["notifications"]
    assert any(item["title"] == "Appointment cancelled" and item["relatedResourceId"] == "APT-002" for item in notifications)

    updates = client.get(f"/api/patients/{PATIENT_ID}/updates", headers=HEADERS).json()["updates"]
    assert any(item["type"] == "appointment_cancelled" and item["resourceId"] == "APT-002" for item in updates)

    audit = client.get("/api/audit-log").json()["entries"]
    assert any(item["action"] == "appointment_cancel" and item["outcome"] == "success" for item in audit)


def test_cardiology_cannot_be_cancelled(client):
    response = client.post("/api/appointments/APT-001/cancel", headers=HEADERS)
    assert response.status_code == 409
    assert "rescheduled" in response.json()["detail"]


def test_non_cardiology_cannot_be_rescheduled(client):
    response = client.post("/api/appointments/APT-002/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS)
    assert response.status_code == 409
    assert "Only Cardiology" in response.json()["detail"]


def test_unavailable_slot(client):
    first = client.post("/api/appointments/APT-001/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS)
    assert first.status_code == 200
    second = client.post("/api/appointments/APT-001/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS)
    assert second.status_code == 409


def test_available_slots_are_deduped_after_repeated_reschedules(client):
    assert client.post("/api/appointments/APT-001/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS).status_code == 200
    slots = client.get("/api/appointments/APT-001/available-slots", headers=HEADERS).json()["slots"]
    datetimes = [slot["datetime"] for slot in slots]

    assert "2026-08-15T10:30:00+08:00" in datetimes
    assert "2026-08-18T09:30:00+08:00" not in datetimes
    assert len(datetimes) == len(set(datetimes))
    assert all(slot["available"] is True for slot in slots)


def test_unknown_appointment(client):
    response = client.post("/api/appointments/NOPE/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS)
    assert response.status_code == 404


def test_missing_rescheduling_permission(client):
    response = client.post(
        "/api/appointments/APT-001/reschedule",
        json={"slotId": "SLOT-001"},
        headers={"X-Caregiver-Id": "CG-002"},
    )
    assert response.status_code == 403
    audit = client.get("/api/audit-log").json()["entries"]
    assert any(item["action"] == "permission_denied" for item in audit)


def test_notification_read_update(client):
    response = client.patch("/api/notifications/NOT-001/read", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["isRead"] is True


def test_demo_reset(client):
    client.post("/api/appointments/APT-001/reschedule", json={"slotId": "SLOT-001"}, headers=HEADERS)
    reset = client.post("/api/demo/reset")
    assert reset.status_code == 200
    appointment = client.get("/api/appointments/APT-001", headers=HEADERS).json()
    assert appointment["datetime"] == "2026-08-15T10:30:00+08:00"


def test_synthetic_markers_in_relevant_responses(client):
    assert client.get(f"/api/patients/{PATIENT_ID}", headers=HEADERS).json()["isSynthetic"] is True
    assert client.get(f"/api/patients/{PATIENT_ID}/overview", headers=HEADERS).json()["isSynthetic"] is True
    assert client.get(f"/api/patients/{PATIENT_ID}/medications", headers=HEADERS).json()["medications"][0]["isSynthetic"] is True


def test_bills_visible_for_sarah(client):
    response = client.get(f"/api/patients/{PATIENT_ID}/bills", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["isSynthetic"] is True
    assert body["bills"][0]["isSynthetic"] is True
    assert body["paymentsEnabled"] is False


def test_health_profiles_are_user_facing(client):
    response = client.get(f"/api/patients/{PATIENT_ID}/health-profiles", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["activeProfileId"] == PATIENT_ID
    assert body["loggedInUser"]["name"] == "Huang Tian"
    assert any(profile["displayName"] == "Mr Jia Sijia" for profile in body["profiles"])
    assert "appointments:read" not in str(body["accessSummary"])


def test_visit_registration_and_refills(client):
    registration = client.get(f"/api/patients/{PATIENT_ID}/visit-registration", headers=HEADERS)
    assert registration.status_code == 200
    assert registration.json()["visits"][0]["canRegister"] is False

    refills = client.get(f"/api/patients/{PATIENT_ID}/medication-refills", headers=HEADERS)
    assert refills.status_code == 200
    assert refills.json()["refillRequestsEnabled"] is True


def test_health_records_do_not_include_agent_todos(client):
    response = client.get(f"/api/patients/{PATIENT_ID}/documents", headers=HEADERS)
    assert response.status_code == 200
    documents = response.json()["documents"]
    assert documents
    assert all(document["followUpActions"] == [] for document in documents)
