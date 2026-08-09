# Caregiver Inbox

Caregiver Inbox is a WorkBuddy-powered AI care-coordination agent that helps family caregivers understand what changed, what matters, and what needs to happen next.

## Problem

Family caregivers receive important care information through fragmented channels, including healthcare applications, family messages, voice notes, documents and calendars.

When information changes, caregivers must manually:

- Identify what changed
- Check whether different sources conflict
- Determine which arrangements are affected
- Inform the relevant family members
- Update calendars and care plans
- Track whether follow-up actions were completed

This creates significant cognitive and administrative burden and may result in missed appointments, outdated information, duplicated work and incomplete handovers.

## Our Solution

Caregiver Inbox connects authorised information sources and converts fragmented care updates into source-linked, human-approved actions.

The agent can:

1. Retrieve updates from authorised sources
2. Compare new information against the confirmed care plan
3. Detect changes, conflicts and unresolved matters
4. Determine which tasks and people are affected
5. Present proposed actions for caregiver approval
6. Update connected tools after approval
7. Track whether actions are acknowledged and completed

## MVP

Our hackathon prototype will demonstrate the following scenario:

1. An appointment is changed in a mock HealthHub-style application.
2. The existing care plan and family message still contain the old date.
3. A helper reports an equipment problem through a simulated messaging source.
4. WorkBuddy retrieves and compares the new information.
5. The agent detects the appointment conflict and unresolved equipment issue.
6. The caregiver reviews the source-linked findings.
7. After approval, the agent:
   - Updates the care plan
   - Updates or creates a calendar event
   - Drafts a message to the relevant family member
   - Creates an appointment-preparation task
   - Records the remaining unresolved matters

## Core Components

- **WorkBuddy Skills** — Six focused skills under `caregiver-inbox-skill/` instead of one monolithic skill: `care-onboarding` (one-time source setup), `care-source-sync` (retrieval), `care-state-diff` (comparison and conflict detection), `care-briefing` (caregiver-facing summary), `care-action-executor` (approval-gated execution), and `caregiver-inbox` (the orchestrator entry point that sequences the rest)
- **CarePortal Sandbox** — Synthetic healthcare portal under `mock-health-portal/` with appointments, documents, notifications, permissions and a connector-ready API
- **Mock HealthHub** — Earlier shorthand for the synthetic healthcare source; this prototype does not claim affiliation with HealthHub
- **Messaging Integration** — WhatsApp via the installed `wacli` skill, scoped to exactly the group chat or phone number(s) the caregiver names during onboarding (asked explicitly, never assumed); carries only synthetic message content even though the transport account is real
- **Confirmed Care State** — `care-data/care-state.json`, `care-data/care-connections.json`, and `care-data/care-action-audit.jsonl`, all in `care-data/` at a fixed location (`~/Desktop/care-data/`, a per-user runtime folder, never committed) — store current appointments, tasks, source connections, and the action history
- **Action Layer** — Auto-updates Google Calendar via `gog` only when sources agree on an appointment *and* there's no busy-time conflict with an existing commitment; everything else (messages via `wacli`, care-plan edits, task assignment) waits for explicit caregiver approval

## Safety and Privacy

All patient and care-plan content in this prototype is synthetic — fictional patient, fictional family members, fictional appointments.

A real account may be linked only as a transport for that synthetic content (e.g. WhatsApp via `wacli`, scoped to exactly the chat or number(s) the caregiver names during setup), never to access real health records or real personal correspondence. See `caregiver-inbox-skill/shared/references/safety-and-source-rules.md` for the full rules.

Caregiver Inbox does not:

- Diagnose medical conditions
- Recommend treatment
- Modify medication instructions
- Resolve conflicting medical information without human confirmation
- Send messages or book appointments without approval
- Auto-update a calendar when sources disagree, or when the proposed time conflicts with an existing commitment
- Access information without explicit authorisation

## Technology

- Tencent WorkBuddy
- Custom WorkBuddy Skills (`caregiver-inbox-skill/`)
- `wacli` — WhatsApp sync/send skill
- `gog` — Google Calendar (and wider Google Workspace) skill
- React
- FastAPI
- SQLite or JSON

## Repository Structure

```text
caregiver-inbox/
├── caregiver-inbox-skill/
│   ├── caregiver-inbox.md        # orchestrator entry point
│   ├── care-onboarding.md        # one-time source setup
│   ├── care-source-sync.md       # retrieval
│   ├── care-state-diff.md        # comparison and conflict detection
│   ├── care-briefing.md          # caregiver-facing summary
│   ├── care-action-executor.md   # approval-gated execution
│   └── shared/                   # references and assets used by all of the above
├── mock-health-portal/           # CarePortal Sandbox (FastAPI + React)
├── caregiver-inbox-demo/         # sample run output
└── archive/                      # superseded docs (e.g. the original single-skill version)
```
