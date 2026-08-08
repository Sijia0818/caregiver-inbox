# CarePortal Sandbox

CarePortal Sandbox is a synthetic healthcare portal for testing a HealthHub-style care-recipient journey in the Age Well hackathon project, Caregiver Inbox.

Synthetic demonstration system - not affiliated with HealthHub, Synapxe, MOH or any healthcare institution. All patients and records are fictional.

## Architecture

- `frontend/` - React, Vite and TypeScript portal UI
- `backend/` - FastAPI REST API with SQLite persistence
- `docs/` - connector-facing contract notes

The frontend calls the backend through the Vite `/api` proxy. The backend uses this demo caregiver header:

```http
X-Caregiver-Id: CG-001
```

This is synthetic demo authentication only. It is not production security.

## Prerequisites

- Python 3.12 or newer compatible runtime
- Node.js 20 or newer

## Backend Setup

```bash
cd mock-health-portal/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`.

OpenAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Frontend Setup

```bash
cd mock-health-portal/frontend
npm install
npm run dev
```

The portal runs at `http://127.0.0.1:5173`.

If the backend is on another host, set:

```bash
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

## Tests

```bash
cd mock-health-portal/backend
python -m pytest
```

Frontend build check:

```bash
cd mock-health-portal/frontend
npm run build
```

## Seed and Reset

The backend creates `backend/data/careportal_sandbox.db` on first run. The seed data is deterministic and includes:

- Patient `SYNTHETIC-001`, Mr Jia Sijia
- Caregivers `CG-001` Huang Tian and `CG-002` Jiang Yu Chen
- Cardiology and physiotherapy appointments
- Synthetic appointment slots
- Notifications, documents, medications, bills and permissions

Reset the demo database:

```bash
curl -X POST http://127.0.0.1:8000/api/demo/reset
```

## Example API Requests

```bash
curl http://127.0.0.1:8000/api/health
```

```bash
curl -H "X-Caregiver-Id: CG-001" \
  http://127.0.0.1:8000/api/patients/SYNTHETIC-001/overview
```

```bash
curl -H "X-Caregiver-Id: CG-001" \
  http://127.0.0.1:8000/api/appointments/APT-001/available-slots
```

```bash
curl -X POST http://127.0.0.1:8000/api/appointments/APT-001/reschedule \
  -H "Content-Type: application/json" \
  -H "X-Caregiver-Id: CG-001" \
  -d '{"slotId":"SLOT-001","reason":"Synthetic demo request"}'
```

```bash
curl -H "X-Caregiver-Id: CG-001" \
  "http://127.0.0.1:8000/api/patients/SYNTHETIC-001/updates?since=2026-08-07T08:00:00+08:00"
```

Developer and connector endpoints such as `/api/audit-log`, `/api/demo/reset` and `/api/patients/{patient_id}/updates` are intentionally not shown as primary portal navigation.

## Current Limitations

- No real authentication, identity proofing or consent management
- No real healthcare portal integration
- No payment processing
- No clinical interpretation, diagnosis or medication recommendations
- Data is synthetic and local to SQLite

## Future WorkBuddy Connector Integration

The connector contract is documented in `docs/connector-contract.md`. The Caregiver Inbox workflow should depend on the generic connector methods, not the SQLite schema or this portal's internal route structure.
