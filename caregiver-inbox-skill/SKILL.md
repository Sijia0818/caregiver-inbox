---
name: caregiver-inbox
description: Care coordination skill for family caregivers supporting an older adult at home. This skill should be used when the user wants WorkBuddy to review authorized care updates, compare them with a confirmed care plan, surface non-clinical changes or conflicts, prepare a concise caregiver briefing, and draft or execute approved coordination actions without giving medical advice.
agent_created: true
---

# Caregiver Inbox

## Overview

Coordinate informal home-care updates for an older adult by retrieving only authorized new information, comparing it with the confirmed care state, surfacing meaningful differences and conflicts, and preparing concise follow-up actions. Keep the work administrative and organizational; never diagnose, prescribe, or resolve medical contradictions independently.

## When to Use

Activate for requests such as:

- "Check Mum's new updates and tell me what needs attention."
- "Prepare today's caregiver briefing."
- "Check whether any appointments have changed."
- "Compare the new updates against the existing care plan."
- "Help me coordinate Mum's appointment."
- "What is still unresolved?"
- "Update the family care plan after I confirm the changes."

## Required Operating Rules

- Inspect current tools and connector availability before claiming access to any source.
- Use only user-authorized sources and only the minimum information required for the task.
- State clearly when a requested source is unavailable, disconnected, unsupported, or cannot be verified.
- Retrieve only information that is new or changed since the last confirmed check when timestamps or state markers exist.
- Compare against the latest confirmed local care state, not against long-term memory.
- Preserve source, source timestamp, confirmation status, relevant evidence, and uncertainty for every meaningful finding.
- Prefer appointment sources in this order: official healthcare portal or API, official appointment letter or hospital document, appointment SMS or email, caregiver-entered record, family message.
- Never silently overwrite conflicting information. Surface the conflict and request human confirmation.
- Never decide which conflicting medical instruction is correct. Direct the caregiver to confirm with the relevant healthcare professional.
- Never judge whether a symptom, medication issue, or equipment issue is safe. Flag it for inspection or professional clarification.
- Require explicit approval before sending messages, editing calendars, updating the confirmed care plan, assigning tasks to other people, sharing personal information, deleting records, or booking, rescheduling, or cancelling appointments.
- When immediate danger or emergency symptoms are mentioned, advise contacting the appropriate emergency or healthcare service immediately. Do not attempt triage.

## Working State

Use simple local JSON files unless the user explicitly requests another format:

- `care-state.json` - latest confirmed care state
- `care-action-audit.jsonl` - append-only action and tool-outcome log

Use the schema in `references/care-state-schema.md`. During development and demos, use only synthetic materials from `assets/demo/` and `references/demo-scenario.md`. Do not store sensitive care data in long-term memory unless the user explicitly authorizes it.

## Workflow

### 1. Establish scope and authorization

- Identify the older adult or synthetic patient.
- Confirm which sources are authorized for the current run.
- Limit retrieval to the narrowest relevant time window and source set.

### 2. Retrieve only new information

- Check timestamps, unread markers, event revision times, file modification times, or prior confirmed-check markers where available.
- Focus on appointments, preparation requirements, care instructions, task changes, completed tasks, caregiver availability, equipment or supply issues, administrative items, and unanswered questions.
- Ignore unrelated conversation and low-value chatter.

### 3. Compare with the confirmed care state

Classify each relevant item as one of:

- New information
- Changed information
- Completed action
- Unresolved question
- Possible contradiction
- Duplicate or already handled
- Informational only

Prioritize differences instead of restating the entire care plan when only a few items changed.

### 4. Detect administrative consequences

Check whether each meaningful change affects:

- Calendar events
- Caregiver availability
- Transport
- Documents or lists to prepare
- Family assignments
- Senior activities
- Equipment arrangements
- Follow-up messages
- Existing tasks and deadlines

Do not infer clinical consequences.

### 5. Resolve source conflicts safely

- Show each conflicting item with source, timestamp, confirmation status, and evidence.
- Use source ranking to guide prioritization, not to erase lower-ranked evidence.
- Request human confirmation before changing the confirmed state when sources disagree.

### 6. Generate the caregiver briefing

Use `assets/caregiver-briefing-template.md` and keep the briefing concise.

Required sections:

- Needs attention now
- Completed
- Waiting for others
- Possible conflicts
- Informational updates

For each action-oriented item, include what changed, why it matters administratively, source and timestamp, current status, recommended next action, and whether approval or professional clarification is required.

### 7. Obtain human approval

Before any consequential external action, show:

- The proposed action
- The supporting source
- The system or file to be modified
- The person to be contacted, if any

Drafting is allowed without sending, but label drafts clearly.

### 8. Execute approved actions

Depending on available tools, do one of the following:

- Update `care-state.json`
- Append to `care-action-audit.jsonl`
- Update a calendar event
- Call an authorized scheduling API
- Draft or send an approved message
- Create an appointment-preparation checklist
- Assign a non-clinical task
- Update a task tracker
- Generate a handover document

If a tool is unavailable, create a reviewable draft or structured action item instead of pretending the action succeeded.

### 9. Close the loop

Track statuses using:

- Proposed
- Awaiting approval
- Approved
- Assigned
- Acknowledged
- Completed
- Blocked
- Requires professional clarification

End each run by stating:

- What was successfully updated
- What remains unresolved
- Who owns each outstanding item
- What should be checked next time

## References and Assets

Load supporting files as needed:

- `references/safety-and-source-rules.md`
- `references/care-state-schema.md`
- `references/demo-scenario.md`
- `assets/caregiver-briefing-template.md`
- `assets/demo/confirmed-care-state.json`
- `assets/demo/incoming-updates.json`
