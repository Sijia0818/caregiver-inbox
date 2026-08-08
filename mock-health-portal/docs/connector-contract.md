# Healthcare Connector Contract

Caregiver Inbox should treat CarePortal Sandbox as one possible implementation of a generic healthcare connector. The skill workflow should not depend on the portal's SQLite schema, seed data, or internal UI.

Synthetic demonstration system - not affiliated with HealthHub, Synapxe, MOH or any healthcare institution. All patients and records are fictional.

## Adapter Boundary

The connector exposes stable, source-linked operations:

```text
get_recent_updates
get_appointments
get_appointment_details
get_available_slots
request_appointment_reschedule
get_health_documents
get_medication_list
get_outstanding_actions
get_caregiver_permissions
```

Each operation should return:

- Source system identifier
- Subject or patient ID
- Retrieval timestamp
- Stable resource IDs
- Source timestamps
- Synthetic-data marker where applicable
- Confirmation or action status
- Minimal evidence required for caregiver coordination

## Suggested Mapping

| Connector method | CarePortal Sandbox endpoint |
| --- | --- |
| `get_recent_updates` | `GET /api/patients/{patient_id}/updates?since={ISO_TIMESTAMP}` |
| `get_appointments` | `GET /api/patients/{patient_id}/appointments` |
| `get_appointment_details` | `GET /api/appointments/{appointment_id}` |
| `get_available_slots` | `GET /api/appointments/{appointment_id}/available-slots` |
| `request_appointment_reschedule` | `POST /api/appointments/{appointment_id}/reschedule` |
| `get_health_documents` | `GET /api/patients/{patient_id}/documents` |
| `get_medication_list` | `GET /api/patients/{patient_id}/medications` |
| `get_outstanding_actions` | `GET /api/patients/{patient_id}/notifications` |
| `get_caregiver_permissions` | `GET /api/patients/{patient_id}/caregivers/{caregiver_id}/permissions` |

## Replacement Strategy

A future officially authorised healthcare-portal adapter could replace this synthetic adapter by implementing the same connector methods. Caregiver Inbox would continue to ask for recent updates, appointments, documents and permissions through the connector boundary, while the adapter handles source-specific authentication, consent checks, API formats and rate limits.

Do not claim that a public HealthHub API exists. Do not claim that official integration is already available. Any production integration would require authorised access, formal consent handling, security review and healthcare-system approval.

## Reschedule Semantics

`request_appointment_reschedule` must enforce permission and slot checks in the adapter or backend service. It should never trust a frontend approval field as the only authorisation control.

Expected result fields:

- Updated appointment
- Previous datetime
- Confirmed new datetime
- Source timestamp
- Audit or request ID
- Outcome
- Failure reason, when unsuccessful

## Data Minimisation

Connectors should return administrative coordination data only. They should not generate diagnostic interpretation, medication advice or safety determinations. When a response includes documents or medication records, the connector should preserve the text exactly as stored and leave interpretation to authorised professionals.
