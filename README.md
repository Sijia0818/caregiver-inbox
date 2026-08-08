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

- **WorkBuddy Skill** — Defines the caregiver-coordination workflow
- **CarePortal Sandbox** — Synthetic healthcare portal under `mock-health-portal/` with appointments, documents, notifications, permissions and a connector-ready API
- **Mock HealthHub** — Earlier shorthand for the synthetic healthcare source; this prototype does not claim affiliation with HealthHub
- **Messaging Integration** — Supplies synthetic caregiver and helper updates
- **Confirmed Care State** — Stores current appointments, tasks and responsibilities
- **Action Layer** — Updates plans, calendars and draft messages after approval

## Safety and Privacy

This prototype uses entirely synthetic data.

Caregiver Inbox does not:

- Diagnose medical conditions
- Recommend treatment
- Modify medication instructions
- Resolve conflicting medical information without human confirmation
- Send messages or book appointments without approval
- Access information without explicit authorisation

## Technology

- Tencent WorkBuddy
- Custom WorkBuddy Skill
- React
- FastAPI
- SQLite or JSON
- Mock healthcare API
- Messaging and calendar connectors

## Repository Structure

```text
caregiver-inbox/
├── workbuddy-skill/
├── mock-health-portal/
├── integration/
├── synthetic-data/
├── docs/
└── demo/
