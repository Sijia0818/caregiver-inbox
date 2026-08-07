# Care State Schema

## Recommended Local Files

### `care-state.json`
Store the latest confirmed non-clinical care state in a single JSON document.

### `care-action-audit.jsonl`
Append one JSON object per action proposal, approval, execution result, or blocked outcome.

Keep both files in the current workspace or another user-approved local folder.

## `care-state.json` Top-Level Shape

```json
{
  "schemaVersion": "1.0",
  "subject": {
    "id": "patient-mdm-lim-mei-ling",
    "displayName": "Mdm Lim Mei Ling",
    "isSynthetic": true
  },
  "lastConfirmedCheck": "2026-08-07T09:00:00+08:00",
  "appointments": [],
  "activeTasks": [],
  "caregiverAssignments": [],
  "equipmentIssues": [],
  "supplyIssues": [],
  "unresolvedQuestions": [],
  "recentChanges": [],
  "actionHistory": []
}
```

## Common Record Fields

Use the same envelope fields across appointments, tasks, assignments, equipment issues, supply issues, unresolved questions, recent changes, and action history records.

| Field | Meaning |
| --- | --- |
| `id` | Stable unique identifier |
| `category` | `appointment`, `task`, `assignment`, `equipment_issue`, `supply_issue`, `question`, `change`, or `action` |
| `description` | Concise plain-language summary |
| `source` | Object describing where the item came from |
| `sourceTimestamp` | Timestamp from the source, if available |
| `lastUpdated` | Last local update timestamp |
| `confirmationStatus` | `confirmed`, `unconfirmed`, `proposed`, or `conflicting` |
| `assignedPerson` | Person responsible, if applicable |
| `actionStatus` | `proposed`, `awaiting_approval`, `approved`, `assigned`, `acknowledged`, `completed`, `blocked`, `requires_professional_clarification`, or `informational` |
| `relatedRecordIds` | IDs of related items |
| `evidenceQuote` | Short quoted or extracted evidence |
| `notes` | Important local notes |
| `uncertainty` | What is unknown or unverified |

## Source Object Shape

```json
{
  "type": "healthcare_api",
  "name": "Mock HealthHub",
  "reference": "appt-update-2026-08-07-001",
  "rank": 1
}
```

## Category Notes

### Appointments
Include date, time, location, purpose, transport notes, preparation requirements, and related caregiver assignments.

### Active Tasks
Use for preparation tasks, follow-up calls, transport planning, paperwork, payments, and reminders.

### Caregiver Assignments
Use for who is expected to accompany, message, buy supplies, inspect equipment, or confirm availability.

### Equipment Issues
Use for walkers, frames, wheelchairs, batteries, chargers, or home-care equipment. Record observations only; do not decide safety.

### Supply Issues
Use for missing forms, consumables, transport passes, reimbursement documents, or home supplies.

### Unresolved Questions
Use for missing confirmations, unanswered messages, unclear instructions, and issues requiring professional clarification.

### Recent Changes
Store a compact diff-style history so later runs can retrieve only what changed.

### Action History
Store the final status of proposals, approvals, tool-confirmed actions, and blocked attempts.

## Example Appointment Record

```json
{
  "id": "appt-cardiology-2026-08-15-1030",
  "category": "appointment",
  "description": "Cardiology appointment moved to 15 August 2026 at 10:30 AM",
  "source": {
    "type": "healthcare_api",
    "name": "Mock HealthHub",
    "reference": "appt-update-2026-08-07-001",
    "rank": 1
  },
  "sourceTimestamp": "2026-08-07T08:15:00+08:00",
  "lastUpdated": "2026-08-07T09:30:00+08:00",
  "confirmationStatus": "unconfirmed",
  "assignedPerson": "Daniel",
  "actionStatus": "awaiting_approval",
  "relatedRecordIds": [
    "assignment-daniel-accompany",
    "task-prepare-medication-list"
  ],
  "evidenceQuote": "Appointment changed to 15 Aug 2026, 10:30 AM. Bring latest medication list.",
  "notes": "Existing confirmed plan still shows 12 Aug 2026.",
  "uncertainty": "Daniel availability on 15 Aug not yet confirmed."
}
```

## Example `care-action-audit.jsonl` Entry

```json
{"timestamp":"2026-08-07T09:35:00+08:00","actionId":"action-draft-message-daniel-001","status":"proposed","target":"Daniel","system":"draft-only","details":"Draft message asking Daniel to confirm availability for 15 Aug 2026 cardiology appointment.","sourceRecordIds":["appt-cardiology-2026-08-15-1030","msg-daniel-leave-2026-08-12"]}
```
