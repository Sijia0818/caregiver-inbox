from __future__ import annotations

import json
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

SINGAPORE_TZ = timezone(timedelta(hours=8))
SG_OFFSET = "+08:00"
PATIENT_ID = "SYNTHETIC-001"
PRIMARY_CAREGIVER_ID = "CG-001"
SOURCE_SYSTEM = "careportal-sandbox"
DISCLAIMER = (
    "Synthetic demonstration system - not affiliated with HealthHub, MOH "
    "or any healthcare institution. All patients and records are fictional."
)


def db_path() -> Path:
    configured = os.environ.get("CAREPORTAL_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "data" / "careportal_sandbox.db"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def now_sg() -> str:
    return datetime.now(SINGAPORE_TZ).replace(microsecond=0).isoformat()


def parse_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def make_audit_id(conn: sqlite3.Connection) -> str:
    return f"AUD-{uuid4().hex[:12].upper()}"


def audit(
    conn: sqlite3.Connection,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str,
    before_value: Any | None = None,
    after_value: Any | None = None,
    failure_reason: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_log (
            id, timestamp, actor_id, action, resource_type, resource_id, outcome,
            before_value, after_value, failure_reason, is_synthetic
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            make_audit_id(conn),
            now_sg(),
            actor_id,
            action,
            resource_type,
            resource_id,
            outcome,
            json.dumps(before_value) if before_value is not None else None,
            json.dumps(after_value) if after_value is not None else None,
            failure_reason,
        ),
    )


def has_permission(conn: sqlite3.Connection, caregiver_id: str, permission: str) -> bool:
    row = conn.execute(
        """
        SELECT allowed FROM caregiver_permissions
        WHERE caregiver_id = ? AND permission = ?
        """,
        (caregiver_id, permission),
    ).fetchone()
    return bool(row and row["allowed"])


def require_permission(
    conn: sqlite3.Connection,
    caregiver_id: str,
    permission: str,
    *,
    resource_type: str,
    resource_id: str,
    action: str,
) -> None:
    if has_permission(conn, caregiver_id, permission):
        return
    audit(
        conn,
        actor_id=caregiver_id,
        action="permission_denied",
        resource_type=resource_type,
        resource_id=resource_id,
        outcome="denied",
        failure_reason=f"Missing permission: {permission}",
    )
    conn.commit()
    raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")


SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS caregivers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS caregiver_permissions (
    caregiver_id TEXT NOT NULL,
    permission TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    is_synthetic INTEGER NOT NULL,
    PRIMARY KEY (caregiver_id, permission)
);

CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    facility TEXT NOT NULL,
    department TEXT NOT NULL,
    datetime TEXT NOT NULL,
    previous_datetime TEXT,
    status TEXT NOT NULL,
    instructions TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    change_history TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS appointment_slots (
    id TEXT PRIMARY KEY,
    appointment_id TEXT NOT NULL,
    department TEXT NOT NULL,
    facility TEXT NOT NULL,
    datetime TEXT NOT NULL,
    available INTEGER NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_resource_id TEXT,
    created_at TEXT NOT NULL,
    is_read INTEGER NOT NULL,
    action_required INTEGER NOT NULL,
    priority TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    facility TEXT NOT NULL,
    specialty TEXT NOT NULL,
    document_date TEXT NOT NULL,
    follow_up_actions TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    sample_content TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS medications (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    prescribed_instruction TEXT NOT NULL,
    refill_status TEXT NOT NULL,
    remaining_refills INTEGER NOT NULL,
    prescribing_facility TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bills (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    facility TEXT NOT NULL,
    service_date TEXT NOT NULL,
    amount TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    due_date TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS updates (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    type TEXT NOT NULL,
    effective_at TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    previous_value TEXT,
    current_value TEXT,
    instructions TEXT NOT NULL,
    is_synthetic INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    before_value TEXT,
    after_value TEXT,
    failure_reason TEXT,
    is_synthetic INTEGER NOT NULL
);
"""


def init_db(reset: bool = False) -> None:
    with connect() as conn:
        if reset:
            conn.executescript(
                """
                DROP TABLE IF EXISTS audit_log;
                DROP TABLE IF EXISTS updates;
                DROP TABLE IF EXISTS bills;
                DROP TABLE IF EXISTS medications;
                DROP TABLE IF EXISTS documents;
                DROP TABLE IF EXISTS notifications;
                DROP TABLE IF EXISTS appointment_slots;
                DROP TABLE IF EXISTS appointments;
                DROP TABLE IF EXISTS caregiver_permissions;
                DROP TABLE IF EXISTS caregivers;
                DROP TABLE IF EXISTS patients;
                """
            )
        conn.executescript(SCHEMA)
        seeded = conn.execute("SELECT COUNT(*) AS c FROM patients").fetchone()["c"]
        if seeded == 0:
            seed(conn)
        conn.commit()


def seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO patients VALUES (?, ?, ?, 1)",
        (PATIENT_ID, "Mr Jia Sijia", 76),
    )
    conn.executemany(
        "INSERT INTO caregivers VALUES (?, ?, ?, 1)",
        [
            (PRIMARY_CAREGIVER_ID, "Huang Tian", "Son"),
            ("CG-002", "Jiang Yu Chen", "Family caregiver"),
        ],
    )
    permissions = {
        "appointments:read": 1,
        "appointments:book": 1,
        "appointments:cancel": 1,
        "appointments:reschedule": 1,
        "notifications:read": 1,
        "documents:read": 1,
        "medications:read": 1,
        "medications:refill": 1,
        "bills:read": 1,
        "payments:write": 0,
        "medications:write": 0,
    }
    conn.executemany(
        "INSERT INTO caregiver_permissions VALUES (?, ?, ?, 1)",
        [(PRIMARY_CAREGIVER_ID, key, value) for key, value in permissions.items()],
    )
    conn.executemany(
        "INSERT INTO caregiver_permissions VALUES (?, ?, ?, 1)",
        [("CG-002", key, 1 if key == "appointments:read" else 0) for key in permissions],
    )
    appointment_history = [
        {
            "timestamp": "2026-08-07T08:15:00+08:00",
            "event": "appointment_rescheduled",
            "previousDatetime": "2026-08-12T10:30:00+08:00",
            "currentDatetime": "2026-08-15T10:30:00+08:00",
            "source": SOURCE_SYSTEM,
        }
    ]
    conn.executemany(
        """
        INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        [
            (
                "APT-001",
                PATIENT_ID,
                "CarePortal General Hospital",
                "Cardiology",
                "2026-08-15T10:30:00+08:00",
                "2026-08-12T10:30:00+08:00",
                "rescheduled",
                json.dumps(["Bring the latest medication list", "Arrive 15 minutes early"]),
                "2026-08-07T08:15:00+08:00",
                json.dumps(appointment_history),
            ),
            (
                "APT-002",
                PATIENT_ID,
                "CarePortal Community Clinic",
                "Physiotherapy",
                "2026-08-22T14:00:00+08:00",
                None,
                "confirmed",
                json.dumps(["Wear comfortable clothing"]),
                "2026-08-02T09:00:00+08:00",
                json.dumps([]),
            ),
        ],
    )
    conn.executemany(
        "INSERT INTO appointment_slots VALUES (?, ?, ?, ?, ?, ?, 1)",
        [
            ("SLOT-001", "APT-001", "Cardiology", "CarePortal General Hospital", "2026-08-18T09:30:00+08:00", 1),
            ("SLOT-002", "APT-001", "Cardiology", "CarePortal General Hospital", "2026-08-18T14:00:00+08:00", 1),
            ("SLOT-003", "APT-001", "Cardiology", "CarePortal General Hospital", "2026-08-20T11:00:00+08:00", 1),
        ],
    )
    conn.executemany(
        "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        [
            ("NOT-001", PATIENT_ID, "appointment", "Cardiology appointment rescheduled", "Cardiology appointment changed from 12 to 15 August 2026.", "APT-001", "2026-08-07T08:15:00+08:00", 0, 1, "high"),
            ("NOT-002", PATIENT_ID, "appointment", "Medication list required", "Bring the latest medication list to the cardiology appointment.", "APT-001", "2026-08-07T08:16:00+08:00", 0, 1, "medium"),
            ("NOT-003", PATIENT_ID, "document", "New discharge summary available", "A discharge summary is available for review.", "DOC-001", "2026-08-06T16:30:00+08:00", 1, 0, "low"),
            ("NOT-004", PATIENT_ID, "medication", "Medication refill may be due", "One medication record has a refill status to review.", "MED-001", "2026-08-06T09:30:00+08:00", 0, 1, "medium"),
            ("NOT-005", PATIENT_ID, "billing", "Outstanding bill due", "A bill is due on 20 August 2026.", "BILL-001", "2026-08-05T12:00:00+08:00", 0, 1, "medium"),
        ],
    )
    conn.executemany(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
        [
            ("DOC-001", PATIENT_ID, "Discharge summary", "CarePortal General Hospital", "General Medicine", "2026-08-06", json.dumps([]), "2026-08-06T16:30:00+08:00", "Sample document - fictional discharge summary."),
            ("DOC-002", PATIENT_ID, "Cardiology appointment letter", "CarePortal General Hospital", "Cardiology", "2026-08-07", json.dumps([]), "2026-08-07T08:15:00+08:00", "Sample document - fictional appointment letter."),
            ("DOC-003", PATIENT_ID, "Lab test results", "CarePortal General Hospital", "Laboratory Medicine", "2026-08-05", json.dumps([]), "2026-08-05T15:45:00+08:00", "Sample document - fictional lab result summary. No diagnostic interpretation is provided."),
            ("DOC-004", PATIENT_ID, "Immunisation record", "National Care Registry", "Preventive Health", "2026-07-30", json.dumps([]), "2026-07-30T10:00:00+08:00", "Sample document - fictional immunisation history."),
            ("DOC-005", PATIENT_ID, "Medical alert and allergy record", "Critical Medical Information System", "Safety Record", "2026-07-28", json.dumps([]), "2026-07-28T09:00:00+08:00", "Sample document - fictional alert/allergy record."),
            ("DOC-006", PATIENT_ID, "Radiology report", "CarePortal General Hospital", "Radiology", "2026-07-20", json.dumps([]), "2026-07-20T14:00:00+08:00", "Sample document - fictional radiology report. No clinical interpretation is provided by this portal."),
        ],
    )
    conn.executemany(
        "INSERT INTO medications VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        [
            ("MED-001", PATIENT_ID, "Amlodipine 5 mg tablet", "Take one tablet every morning.", "may_be_due", 1, "CarePortal General Hospital", "2026-08-06T09:30:00+08:00"),
            ("MED-002", PATIENT_ID, "Metformin 500 mg tablet", "Take one tablet twice daily after meals.", "current", 3, "CarePortal Community Clinic", "2026-08-01T10:00:00+08:00"),
        ],
    )
    conn.executemany(
        "INSERT INTO bills VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        [
            ("BILL-001", PATIENT_ID, "CarePortal General Hospital", "2026-08-01", "SGD 86.40", "outstanding", "2026-08-20"),
            ("BILL-002", PATIENT_ID, "CarePortal Community Clinic", "2026-07-20", "SGD 24.00", "paid", "2026-08-05"),
        ],
    )
    conn.execute(
        "INSERT INTO updates VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            "UPDATE-001",
            PATIENT_ID,
            "appointment_rescheduled",
            "2026-08-07T08:15:00+08:00",
            "APT-001",
            json.dumps({"datetime": "2026-08-12T10:30:00+08:00"}),
            json.dumps({"datetime": "2026-08-15T10:30:00+08:00"}),
            json.dumps(["Bring the latest medication list"]),
        ),
    )


def ensure_db():
    init_db(reset=False)
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def appointment_payload(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row)
    data["instructions"] = parse_json(data.pop("instructions"), [])
    data["changeHistory"] = parse_json(data.pop("change_history"), [])
    data["previousDatetime"] = data.pop("previous_datetime")
    data["lastUpdated"] = data.pop("last_updated")
    data["patientId"] = data.pop("patient_id")
    data["isSynthetic"] = bool(data.pop("is_synthetic"))
    return data


def notification_payload(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row)
    data["patientId"] = data.pop("patient_id")
    data["relatedResourceId"] = data.pop("related_resource_id")
    data["createdAt"] = data.pop("created_at")
    data["isRead"] = bool(data.pop("is_read"))
    data["actionRequired"] = bool(data.pop("action_required"))
    data["isSynthetic"] = bool(data.pop("is_synthetic"))
    return data


def document_payload(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row)
    data["patientId"] = data.pop("patient_id")
    data["documentType"] = data.pop("document_type")
    data["documentDate"] = data.pop("document_date")
    data["followUpActions"] = parse_json(data.pop("follow_up_actions"), [])
    data["lastUpdated"] = data.pop("last_updated")
    data["sampleContent"] = data.pop("sample_content")
    data["isSynthetic"] = bool(data.pop("is_synthetic"))
    return data


def medication_payload(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row)
    data["patientId"] = data.pop("patient_id")
    data["prescribedInstruction"] = data.pop("prescribed_instruction")
    data["refillStatus"] = data.pop("refill_status")
    data["remainingRefills"] = data.pop("remaining_refills")
    data["prescribingFacility"] = data.pop("prescribing_facility")
    data["lastUpdated"] = data.pop("last_updated")
    data["isSynthetic"] = bool(data.pop("is_synthetic"))
    return data


def bill_payload(row: sqlite3.Row) -> dict[str, Any]:
    data = row_to_dict(row)
    data["patientId"] = data.pop("patient_id")
    data["serviceDate"] = data.pop("service_date")
    data["paymentStatus"] = data.pop("payment_status")
    data["dueDate"] = data.pop("due_date")
    data["isSynthetic"] = bool(data.pop("is_synthetic"))
    return data


def restored_slot_id(appointment_id: str, datetime_value: str) -> str:
    compact = (
        datetime_value.replace("-", "")
        .replace(":", "")
        .replace("+", "")
        .replace("T", "-")
    )
    return f"SLOT-RETURNED-{appointment_id}-{compact}"


class RescheduleRequest(BaseModel):
    slotId: str
    reason: str | None = None


class AppointmentBookingRequest(BaseModel):
    facility: str
    department: str
    date: str
    reason: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db(reset=False)
    yield


app = FastAPI(
    title="CarePortal Sandbox API",
    description=f"{DISCLAIMER} Demo authentication uses X-Caregiver-Id and is not production security.",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "sourceSystem": SOURCE_SYSTEM,
        "isSynthetic": True,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/patients/{patient_id}")
def get_patient(patient_id: str, conn: sqlite3.Connection = Depends(ensure_db)) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    data = row_to_dict(row)
    data["isSynthetic"] = bool(data["is_synthetic"])
    del data["is_synthetic"]
    return data


@app.get("/api/patients/{patient_id}/overview")
def get_overview(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "appointments:read", resource_type="patient", resource_id=patient_id, action="overview")
    require_permission(conn, x_caregiver_id, "notifications:read", resource_type="patient", resource_id=patient_id, action="overview")
    patient = get_patient(patient_id, conn)
    caregiver = conn.execute("SELECT * FROM caregivers WHERE id = ?", (x_caregiver_id,)).fetchone()
    next_appt = conn.execute(
        "SELECT * FROM appointments WHERE patient_id = ? AND status != 'cancelled' ORDER BY datetime LIMIT 1",
        (patient_id,),
    ).fetchone()
    notifications = [
        notification_payload(row)
        for row in conn.execute(
            "SELECT * FROM notifications WHERE patient_id = ? ORDER BY created_at DESC LIMIT 3",
            (patient_id,),
        ).fetchall()
    ]
    outstanding_actions = [item for item in notifications if item["actionRequired"] and not item["isRead"]]
    medication = conn.execute(
        "SELECT * FROM medications WHERE patient_id = ? AND refill_status != 'current' LIMIT 1",
        (patient_id,),
    ).fetchone()
    if has_permission(conn, x_caregiver_id, "bills:read"):
        bill = conn.execute(
            "SELECT COUNT(*) AS c FROM bills WHERE patient_id = ? AND payment_status = 'outstanding'",
            (patient_id,),
        ).fetchone()
        bill_summary = {"restricted": False, "outstandingCount": bill["c"], "message": "Bill details available."}
    else:
        bill_summary = {"restricted": True, "outstandingCount": None, "message": "Bill details are unavailable for this profile."}
    return {
        "sourceSystem": SOURCE_SYSTEM,
        "isSynthetic": True,
        "disclaimer": DISCLAIMER,
        "patient": patient,
        "authorizedCaregiver": row_to_dict(caregiver) if caregiver else None,
        "nextAppointment": appointment_payload(next_appt) if next_appt else None,
        "recentNotifications": notifications,
        "outstandingAdministrativeActions": outstanding_actions,
        "medicationRefillStatus": medication_payload(medication) if medication else {"status": "current", "isSynthetic": True},
        "outstandingBillSummary": bill_summary,
    }


@app.get("/api/patients/{patient_id}/appointments")
def get_appointments(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "appointments:read", resource_type="appointments", resource_id=patient_id, action="retrieve_appointments")
    rows = conn.execute("SELECT * FROM appointments WHERE patient_id = ? ORDER BY datetime", (patient_id,)).fetchall()
    return {"isSynthetic": True, "appointments": [appointment_payload(row) for row in rows]}


@app.get("/api/appointments/{appointment_id}")
def get_appointment(
    appointment_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "appointments:read", resource_type="appointment", resource_id=appointment_id, action="retrieve_appointment")
    row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment_payload(row)


@app.post("/api/patients/{patient_id}/appointments")
def book_appointment(
    patient_id: str,
    payload: AppointmentBookingRequest,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    get_patient(patient_id, conn)
    require_permission(conn, x_caregiver_id, "appointments:book", resource_type="appointment", resource_id=patient_id, action="appointment_book")

    facility = payload.facility.strip()
    department = payload.department.strip()
    if not facility or not department:
        raise HTTPException(status_code=422, detail="Institution and service are required")
    try:
        selected_date = datetime.fromisoformat(payload.date).date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Use a valid appointment date") from exc
    if selected_date < datetime.now(SINGAPORE_TZ).date():
        raise HTTPException(status_code=422, detail="Choose today or a future date")

    appointment_datetime = datetime.combine(selected_date, datetime.min.time(), tzinfo=SINGAPORE_TZ).replace(hour=9).isoformat()
    display_date = selected_date.strftime("%d %B %Y")
    appointment_id = f"APT-{uuid4().hex[:8].upper()}"
    created_at = now_sg()
    instructions = ["Bring identification", "Arrive 15 minutes early"]
    conn.execute(
        """
        INSERT INTO appointments
        VALUES (?, ?, ?, ?, ?, NULL, 'confirmed', ?, ?, ?, 1)
        """,
        (
            appointment_id,
            patient_id,
            facility,
            department,
            appointment_datetime,
            json.dumps(instructions),
            created_at,
            json.dumps(
                [
                    {
                        "timestamp": created_at,
                        "event": "appointment_booked",
                        "currentDatetime": appointment_datetime,
                        "source": SOURCE_SYSTEM,
                        "actor": x_caregiver_id,
                    }
                ]
            ),
        ),
    )
    notification_id = f"NOT-{uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 'medium', 1)",
        (
            notification_id,
            patient_id,
            "appointment",
            "Appointment booked",
            f"{department} appointment booked at {facility} on {display_date} at 9:00 AM.",
            appointment_id,
            created_at,
        ),
    )
    update_id = f"UPDATE-{uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO updates VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            update_id,
            patient_id,
            "appointment_booked",
            created_at,
            appointment_id,
            None,
            json.dumps({"datetime": appointment_datetime, "facility": facility, "department": department}),
            json.dumps(instructions),
        ),
    )
    appointment = appointment_payload(conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone())
    audit(
        conn,
        actor_id=x_caregiver_id,
        action="appointment_book",
        resource_type="appointment",
        resource_id=appointment_id,
        outcome="success",
        after_value=appointment,
    )
    conn.commit()
    return {"isSynthetic": True, "message": "Appointment booked.", "appointment": appointment}


@app.get("/api/appointments/{appointment_id}/available-slots")
def get_slots(
    appointment_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "appointments:read", resource_type="appointment", resource_id=appointment_id, action="retrieve_slots")
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment["department"] != "Cardiology" or appointment["status"] == "cancelled":
        return {"isSynthetic": True, "slots": []}
    rows = conn.execute(
        """
        SELECT MIN(id) AS id, appointment_id, department, facility, datetime, MAX(available) AS available, MAX(is_synthetic) AS is_synthetic
        FROM appointment_slots
        WHERE appointment_id = ? AND available = 1
        GROUP BY appointment_id, department, facility, datetime
        ORDER BY datetime
        """,
        (appointment_id,),
    ).fetchall()
    return {
        "isSynthetic": True,
        "slots": [
            {
                "id": row["id"],
                "appointmentId": row["appointment_id"],
                "department": row["department"],
                "facility": row["facility"],
                "datetime": row["datetime"],
                "available": bool(row["available"]),
                "isSynthetic": bool(row["is_synthetic"]),
            }
            for row in rows
        ],
    }


@app.post("/api/appointments/{appointment_id}/reschedule")
def reschedule(
    appointment_id: str,
    payload: RescheduleRequest,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    before = appointment_payload(appointment) if appointment else None
    audit(
        conn,
        actor_id=x_caregiver_id,
        action="request_appointment_reschedule",
        resource_type="appointment",
        resource_id=appointment_id,
        outcome="received",
        before_value=before,
        after_value={"slotId": payload.slotId},
    )
    if not appointment:
        audit(conn, actor_id=x_caregiver_id, action="appointment_reschedule", resource_type="appointment", resource_id=appointment_id, outcome="failed", failure_reason="Unknown appointment")
        conn.commit()
        raise HTTPException(status_code=404, detail="Appointment not found")
    require_permission(conn, x_caregiver_id, "appointments:reschedule", resource_type="appointment", resource_id=appointment_id, action="appointment_reschedule")
    if appointment["department"] != "Cardiology":
        audit(conn, actor_id=x_caregiver_id, action="appointment_reschedule", resource_type="appointment", resource_id=appointment_id, outcome="failed", failure_reason="Rescheduling is only available for Cardiology in this demo")
        conn.commit()
        raise HTTPException(status_code=409, detail="Only Cardiology appointments can be rescheduled in this demo")
    if appointment["status"] == "cancelled":
        audit(conn, actor_id=x_caregiver_id, action="appointment_reschedule", resource_type="appointment", resource_id=appointment_id, outcome="failed", failure_reason="Appointment already cancelled")
        conn.commit()
        raise HTTPException(status_code=409, detail="Cancelled appointments cannot be rescheduled")
    slot = conn.execute(
        "SELECT * FROM appointment_slots WHERE appointment_id = ? AND id = ?",
        (appointment_id, payload.slotId),
    ).fetchone()
    if not slot:
        audit(conn, actor_id=x_caregiver_id, action="appointment_reschedule", resource_type="slot", resource_id=payload.slotId, outcome="failed", failure_reason="Unknown slot")
        conn.commit()
        raise HTTPException(status_code=404, detail="Slot not found")
    if not slot["available"]:
        audit(conn, actor_id=x_caregiver_id, action="appointment_reschedule", resource_type="slot", resource_id=payload.slotId, outcome="failed", failure_reason="Slot unavailable")
        conn.commit()
        raise HTTPException(status_code=409, detail="Slot is unavailable")

    previous_datetime = appointment["datetime"]
    new_datetime = slot["datetime"]
    history = parse_json(appointment["change_history"], [])
    history.append(
        {
            "timestamp": now_sg(),
            "event": "appointment_rescheduled",
            "previousDatetime": previous_datetime,
            "currentDatetime": new_datetime,
            "source": SOURCE_SYSTEM,
            "actor": x_caregiver_id,
        }
    )
    conn.execute(
        """
        UPDATE appointments
        SET datetime = ?, previous_datetime = ?, status = 'rescheduled', last_updated = ?, change_history = ?
        WHERE id = ?
        """,
        (new_datetime, previous_datetime, now_sg(), json.dumps(history), appointment_id),
    )
    conn.execute("UPDATE appointment_slots SET available = 0 WHERE appointment_id = ? AND datetime = ?", (appointment_id, new_datetime))
    existing_previous_slot = conn.execute(
        "SELECT id FROM appointment_slots WHERE appointment_id = ? AND datetime = ? LIMIT 1",
        (appointment_id, previous_datetime),
    ).fetchone()
    if existing_previous_slot:
        conn.execute("UPDATE appointment_slots SET available = 1 WHERE appointment_id = ? AND datetime = ?", (appointment_id, previous_datetime))
    else:
        conn.execute(
            """
            INSERT INTO appointment_slots
            VALUES (?, ?, ?, ?, ?, 1, 1)
            """,
            (
                restored_slot_id(appointment_id, previous_datetime),
                appointment_id,
                appointment["department"],
                appointment["facility"],
                previous_datetime,
            ),
        )
    notification_id = f"NOT-{uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 'high', 1)",
        (
            notification_id,
            appointment["patient_id"],
            "appointment",
            "Reschedule confirmed",
            f"{appointment['department']} appointment moved from {previous_datetime} to {new_datetime}.",
            appointment_id,
            now_sg(),
        ),
    )
    update_id = f"UPDATE-{uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO updates VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            update_id,
            appointment["patient_id"],
            "appointment_rescheduled",
            now_sg(),
            appointment_id,
            json.dumps({"datetime": previous_datetime}),
            json.dumps({"datetime": new_datetime}),
            appointment["instructions"],
        ),
    )
    updated_row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    updated = appointment_payload(updated_row)
    audit(
        conn,
        actor_id=x_caregiver_id,
        action="appointment_reschedule",
        resource_type="appointment",
        resource_id=appointment_id,
        outcome="success",
        before_value={"datetime": previous_datetime},
        after_value={"datetime": new_datetime, "slotId": payload.slotId, "notificationId": notification_id},
    )
    conn.commit()
    return {"isSynthetic": True, "message": "Rescheduling request confirmed.", "appointment": updated}


@app.post("/api/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    appointment = conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone()
    before = appointment_payload(appointment) if appointment else None
    audit(
        conn,
        actor_id=x_caregiver_id,
        action="request_appointment_cancel",
        resource_type="appointment",
        resource_id=appointment_id,
        outcome="received",
        before_value=before,
    )
    if not appointment:
        audit(conn, actor_id=x_caregiver_id, action="appointment_cancel", resource_type="appointment", resource_id=appointment_id, outcome="failed", failure_reason="Unknown appointment")
        conn.commit()
        raise HTTPException(status_code=404, detail="Appointment not found")
    require_permission(conn, x_caregiver_id, "appointments:cancel", resource_type="appointment", resource_id=appointment_id, action="appointment_cancel")
    if appointment["department"] == "Cardiology":
        audit(conn, actor_id=x_caregiver_id, action="appointment_cancel", resource_type="appointment", resource_id=appointment_id, outcome="failed", failure_reason="Cardiology is reschedule-only in this demo")
        conn.commit()
        raise HTTPException(status_code=409, detail="Cardiology appointments can be rescheduled, not cancelled, in this demo")
    if appointment["status"] == "cancelled":
        audit(conn, actor_id=x_caregiver_id, action="appointment_cancel", resource_type="appointment", resource_id=appointment_id, outcome="failed", failure_reason="Appointment already cancelled")
        conn.commit()
        raise HTTPException(status_code=409, detail="Appointment is already cancelled")

    cancelled_at = now_sg()
    history = parse_json(appointment["change_history"], [])
    history.append(
        {
            "timestamp": cancelled_at,
            "event": "appointment_cancelled",
            "previousDatetime": appointment["datetime"],
            "source": SOURCE_SYSTEM,
            "actor": x_caregiver_id,
        }
    )
    conn.execute(
        """
        UPDATE appointments
        SET status = 'cancelled', last_updated = ?, change_history = ?
        WHERE id = ?
        """,
        (cancelled_at, json.dumps(history), appointment_id),
    )
    notification_id = f"NOT-{uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO notifications VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, 'medium', 1)",
        (
            notification_id,
            appointment["patient_id"],
            "appointment",
            "Appointment cancelled",
            f"{appointment['department']} appointment at {appointment['facility']} has been cancelled.",
            appointment_id,
            cancelled_at,
        ),
    )
    update_id = f"UPDATE-{uuid4().hex[:8].upper()}"
    conn.execute(
        "INSERT INTO updates VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (
            update_id,
            appointment["patient_id"],
            "appointment_cancelled",
            cancelled_at,
            appointment_id,
            json.dumps({"status": appointment["status"], "datetime": appointment["datetime"]}),
            json.dumps({"status": "cancelled", "datetime": appointment["datetime"]}),
            appointment["instructions"],
        ),
    )
    updated = appointment_payload(conn.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone())
    audit(
        conn,
        actor_id=x_caregiver_id,
        action="appointment_cancel",
        resource_type="appointment",
        resource_id=appointment_id,
        outcome="success",
        before_value=before,
        after_value=updated,
    )
    conn.commit()
    return {"isSynthetic": True, "message": "Appointment cancelled.", "appointment": updated}


@app.get("/api/patients/{patient_id}/notifications")
def get_notifications(
    patient_id: str,
    since: str | None = Query(None),
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "notifications:read", resource_type="notifications", resource_id=patient_id, action="retrieve_notifications")
    if since:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE patient_id = ? AND created_at > ? ORDER BY created_at DESC",
            (patient_id, since),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notifications WHERE patient_id = ? ORDER BY created_at DESC", (patient_id,)).fetchall()
    return {"isSynthetic": True, "notifications": [notification_payload(row) for row in rows]}


@app.patch("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "notifications:read", resource_type="notification", resource_id=notification_id, action="mark_notification_read")
    row = conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Notification not found")
    before = notification_payload(row)
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    after = notification_payload(conn.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone())
    audit(conn, actor_id=x_caregiver_id, action="mark_notification_read", resource_type="notification", resource_id=notification_id, outcome="success", before_value=before, after_value=after)
    conn.commit()
    return after


@app.get("/api/patients/{patient_id}/documents")
def get_documents(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "documents:read", resource_type="documents", resource_id=patient_id, action="retrieve_documents")
    rows = conn.execute("SELECT * FROM documents WHERE patient_id = ? ORDER BY document_date DESC", (patient_id,)).fetchall()
    return {"isSynthetic": True, "documents": [document_payload(row) for row in rows]}


@app.get("/api/patients/{patient_id}/medications")
def get_medications(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "medications:read", resource_type="medications", resource_id=patient_id, action="retrieve_medications")
    rows = conn.execute("SELECT * FROM medications WHERE patient_id = ? ORDER BY display_name", (patient_id,)).fetchall()
    return {"isSynthetic": True, "medications": [medication_payload(row) for row in rows]}


@app.get("/api/patients/{patient_id}/bills")
def get_bills(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "bills:read", resource_type="bills", resource_id=patient_id, action="retrieve_bills")
    rows = conn.execute("SELECT * FROM bills WHERE patient_id = ? ORDER BY due_date", (patient_id,)).fetchall()
    return {"isSynthetic": True, "bills": [bill_payload(row) for row in rows], "paymentsEnabled": False}


@app.get("/api/patients/{patient_id}/caregivers/{caregiver_id}/permissions")
def get_permissions(
    patient_id: str,
    caregiver_id: str,
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    caregiver = conn.execute("SELECT * FROM caregivers WHERE id = ?", (caregiver_id,)).fetchone()
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")
    rows = conn.execute("SELECT permission, allowed, is_synthetic FROM caregiver_permissions WHERE caregiver_id = ? ORDER BY permission", (caregiver_id,)).fetchall()
    return {
        "patientId": patient_id,
        "caregiver": {"id": caregiver["id"], "name": caregiver["name"], "relationship": caregiver["relationship"], "isSynthetic": bool(caregiver["is_synthetic"])},
        "demoAuthentication": "Use X-Caregiver-Id. Demo authentication only; not production security.",
        "permissions": [{"permission": row["permission"], "allowed": bool(row["allowed"]), "isSynthetic": bool(row["is_synthetic"])} for row in rows],
        "isSynthetic": True,
    }


@app.get("/api/patients/{patient_id}/health-profiles")
def get_health_profiles(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    patient = get_patient(patient_id, conn)
    acting = conn.execute("SELECT * FROM caregivers WHERE id = ?", (x_caregiver_id,)).fetchone()
    family = conn.execute("SELECT * FROM caregivers WHERE id != ? ORDER BY id", (x_caregiver_id,)).fetchall()
    if not acting:
        raise HTTPException(status_code=404, detail="Caregiver not found")
    permissions = conn.execute(
        "SELECT permission, allowed FROM caregiver_permissions WHERE caregiver_id = ? ORDER BY permission",
        (x_caregiver_id,),
    ).fetchall()
    full_access = all(row["allowed"] for row in permissions if row["permission"] != "payments:write" and row["permission"] != "medications:write")
    access_items = [
        "Appointments and visit registration",
        "Health records",
        "Medication list and refill requests",
        "Bills and payment tracking",
        "Notifications",
    ]
    return {
        "isSynthetic": True,
        "activeProfileId": patient_id,
        "loggedInUser": {
            "id": acting["id"],
            "name": acting["name"],
            "relationship": acting["relationship"],
            "profileType": "caregiver",
            "isSynthetic": bool(acting["is_synthetic"]),
        },
        "profiles": [
            {
                "id": acting["id"],
                "displayName": acting["name"],
                "relationship": "Self",
                "profileType": "caregiver",
                "accessStatus": "Logged in",
                "isSynthetic": True,
            },
            {
                "id": patient["id"],
                "displayName": patient["name"],
                "relationship": "Care recipient",
                "profileType": "care_recipient",
                "accessStatus": "Full demo access" if full_access else "Limited demo access",
                "isSynthetic": True,
            },
            *[
                {
                    "id": row["id"],
                    "displayName": row["name"],
                    "relationship": row["relationship"],
                    "profileType": "family_caregiver",
                    "accessStatus": "Family profile on record",
                    "isSynthetic": bool(row["is_synthetic"]),
                }
                for row in family
            ],
        ],
        "accessSummary": {
            "status": "Full demo access" if full_access else "Limited demo access",
            "items": access_items,
            "note": "This portal uses a demo header to simulate profile access. It is not production authentication.",
        },
    }


@app.get("/api/patients/{patient_id}/visit-registration")
def get_visit_registration(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "appointments:read", resource_type="visit_registration", resource_id=patient_id, action="retrieve_visit_registration")
    next_appt = conn.execute(
        "SELECT * FROM appointments WHERE patient_id = ? AND status != 'cancelled' ORDER BY datetime LIMIT 1",
        (patient_id,),
    ).fetchone()
    if not next_appt:
        return {"isSynthetic": True, "visits": [], "message": "No upcoming visits available for registration."}
    appointment = appointment_payload(next_appt)
    return {
        "isSynthetic": True,
        "visits": [
            {
                "id": f"VISIT-{appointment['id']}",
                "appointmentId": appointment["id"],
                "facility": appointment["facility"],
                "department": appointment["department"],
                "datetime": appointment["datetime"],
                "registrationStatus": "not_open",
                "queueNumber": None,
                "canRegister": False,
                "registrationWindow": "30 to 90 minutes before appointment time",
                "message": "Mobile registration is not open yet.",
            }
        ],
    }


@app.get("/api/patients/{patient_id}/medication-refills")
def get_medication_refills(
    patient_id: str,
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "medications:read", resource_type="medication_refills", resource_id=patient_id, action="retrieve_medication_refills")
    medications = [medication_payload(row) for row in conn.execute("SELECT * FROM medications WHERE patient_id = ? ORDER BY display_name", (patient_id,)).fetchall()]
    return {
        "isSynthetic": True,
        "refillRequestsEnabled": has_permission(conn, x_caregiver_id, "medications:refill"),
        "message": "Refill requests do not change medication instructions or provide clinical recommendations.",
        "requests": [
            {
                "id": "REFILL-001",
                "medicationId": "MED-001",
                "displayName": "Amlodipine 5 mg tablet",
                "status": "ready_to_request",
                "collectionOptions": ["Delivery with OTP", "Pharmacy self-collection", "Locker self-collection"],
                "lastUpdated": "2026-08-06T09:30:00+08:00",
                "isSynthetic": True,
            }
        ],
        "medications": medications,
    }


@app.get("/api/audit-log")
def get_audit_log(conn: sqlite3.Connection = Depends(ensure_db)) -> dict[str, Any]:
    rows = conn.execute("SELECT * FROM audit_log ORDER BY timestamp DESC, id DESC").fetchall()
    return {
        "isSynthetic": True,
        "entries": [
            {
                "auditId": row["id"],
                "timestamp": row["timestamp"],
                "actor": row["actor_id"],
                "action": row["action"],
                "resourceType": row["resource_type"],
                "resourceId": row["resource_id"],
                "outcome": row["outcome"],
                "beforeValue": parse_json(row["before_value"], None),
                "afterValue": parse_json(row["after_value"], None),
                "failureReason": row["failure_reason"],
                "isSynthetic": bool(row["is_synthetic"]),
            }
            for row in rows
        ],
    }


@app.post("/api/demo/reset")
def reset_demo(response: Response) -> dict[str, Any]:
    init_db(reset=True)
    response.status_code = 200
    return {"status": "reset", "isSynthetic": True, "message": "Database restored to original state."}


@app.get("/api/patients/{patient_id}/updates")
def get_updates(
    patient_id: str,
    since: str | None = Query(None),
    x_caregiver_id: str = Header(PRIMARY_CAREGIVER_ID, alias="X-Caregiver-Id"),
    conn: sqlite3.Connection = Depends(ensure_db),
) -> dict[str, Any]:
    require_permission(conn, x_caregiver_id, "appointments:read", resource_type="updates", resource_id=patient_id, action="retrieve_updates")
    if since:
        rows = conn.execute(
            "SELECT * FROM updates WHERE patient_id = ? AND effective_at > ? ORDER BY effective_at",
            (patient_id, since),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM updates WHERE patient_id = ? ORDER BY effective_at", (patient_id,)).fetchall()
    return {
        "sourceSystem": SOURCE_SYSTEM,
        "subjectId": patient_id,
        "retrievedAt": now_sg(),
        "isSynthetic": True,
        "updates": [
            {
                "id": row["id"],
                "type": row["type"],
                "effectiveAt": row["effective_at"],
                "resourceId": row["resource_id"],
                "previousValue": parse_json(row["previous_value"], None),
                "currentValue": parse_json(row["current_value"], None),
                "instructions": parse_json(row["instructions"], []),
                "isSynthetic": bool(row["is_synthetic"]),
            }
            for row in rows
        ],
    }
