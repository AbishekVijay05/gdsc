# Implementation Plan: Conversational Orchestrator

> Transform the static one-shot drug repurposing system into an interactive, stateful, conversational research partner.

---

## Current System

- User enters a drug name → 6 agents run in parallel → one static report is generated
- Basic followup Q&A (`/followup`) is stateless — each question is independent
- No conversation memory, no constraint translation, no candidate steering
- Single `/analyze` endpoint, no interactive loop

## Target System (from spec)

| Capability | Description |
|---|---|
| **Intent-to-Constraint Translation** | Convert casual feedback into hard agent constraints |
| **Conversational State Management** | Persistent chat history, rejected candidates, context across turns |
| **Asynchronous Coordination** | Fluid chat UI while complex multi-domain retrieval runs in background |
| **Proactive Clarification** | Identify ambiguous feedback and ask clarifying questions |
| **Simulation Mode** | Add mid-search constraints, reject candidates, trigger AI clarification |

---

## 1. Backend: Conversation State Manager

**New file:** `backend/modules/conversation_state.py`

- In-memory dictionary keyed by `session_id`
- Tracks per session:
  - Complete chat history (user messages + AI responses)
  - Active constraints (accumulated from each turn)
  - Rejected candidate list (with rejection reasons)
  - Last full pipeline result (to avoid re-running unnecessarily)
  - Clarification state (pending questions waiting for user response)
- Auto-cleanup after inactivity timeout

---

## 2. Backend: Intent-to-Constraint Translator

**New file:** `backend/modules/intent_translator.py`

- Uses LLM (NVIDIA NIM via existing API key) to parse natural language into structured constraints
- **Input:** User message + current pipeline results + current constraints
- **Output:** Structured dict with:
  - `new_constraints` — e.g. `{exclude_cardiovascular: true}`
  - `rejected_candidates` — drug names to exclude
  - `clarification_needed` — boolean
  - `clarification_question` — string (if clarification needed)
  - `intent_type` — one of: `add_constraint`, `reject_candidate`, `new_search`, `clarification`, `general_question`, `ambiguous`
- **Examples:**
  - *"gentler on the heart"* → `{exclude: ["cardiovascular toxicity"], exclude_organ: "heart_side_effects"}`
  - *"Must cross the blood-brain barrier"* → `{require_bbb: True}`
  - *"Too expensive to manufacture"* → `{exclude_manufacturing_cost_high: True, clarification: None}`
  - *"I'm looking for something for sleep issues"* → `{intent_type: "ambiguous", clarification_question: "Do you mean insomnia related to anxiety, or sleep apnea? These involve different pathways."}`

---

## 3. Backend: Pipeline with Constraints

**Modify:** `backend/app.py` — `run_pipeline()` function

- Add `constraints` parameter to `run_pipeline(molecule, language, constraints=None)`
- Constraints affect:
  - **Clinical:** Filter trials matching/excluding certain conditions
  - **Synthesizer:** Exclude rejected candidates from report generation
  - **Scorer:** Adjust scores for rejected candidates
- The pipeline still returns the same data structure, but filtered

---

## 4. Backend: New Endpoints

**Modify:** `backend/app.py`

### `POST /chat`
```json
Input: { "session_id": "...", "message": "be gentler on the heart" }
Output: {
  "response_type": "update" | "new_candidates" | "clarification" | "answer",
  "message": "Understood. Excluding cardiovascular toxicity...",
  "updated_candidates": [...],
  "active_constraints": ["exclude_cardiovascular"],
  "agent_status": {"clinical": "active", "patent": "complete", ...},
  "clarification_question": null
}
```

### `POST /reject-candidate`
```json
Input: { "session_id": "...", "drug_name": "Metformin", "reason": "Too expensive" }
Output: { "status": "ok", "active_constraints": [...], "remaining_candidates": [...] }
```

### `GET /session/{session_id}`
```json
Output: {
  "history": [...],
  "active_constraints": [...],
  "rejected_candidates": [{"drug": "...", "reason": "..."}]
}
```

---

## 5. Frontend: Persistent Chat Interface

**Modify:** `frontend/templates/index.html` + `frontend/static/js/main.js` + `frontend/static/css/style.css`

### New Chat Panel (under Repurpose tab or as new "Chat" tab)

- **Message area:** Continuous dialogue window with user/AI message bubbles
- **Input:** Text input + "Send" button at bottom
- **Inline result cards:** Drug candidates rendered directly in the chat flow
  - Each card shows: drug name, confidence score, brief rationale
  - **Reject button** on each card → feeds back into `/reject-candidate`
  - **Analyze button** → opens full report sidebar

### Active Constraints Display

- Top of chat panel shows active constraints as tags/pills
- Each pill has an ✕ to remove that constraint

### Conversation Steering

- Quick-action buttons: "Add biological constraint", "Reject candidate", "Start new analysis"
- "Must cross blood-brain barrier" toggle
- Vague feedback detection → shows clarification dialog from AI response

---

## 6. Frontend: Live Agent Activity Feed

**Modify:** `frontend/templates/index.html` + `frontend/static/js/main.js` + `frontend/static/css/style.css`

### Sidebar / bottom feed showing:
- Real-time agent status: "Clinical: Searching trials...", "Patent: Checking IP...", etc.
- Polls `/session/{id}` every 1-2s during active analysis
- Animated status indicators (spinning icon while active, checkmark when done)
- Collapsible feed to save space

---

## Files Summary

| Action | File | Changes |
|---|---|---|
| **Create** | `backend/modules/conversation_state.py` | Session state management |
| **Create** | `backend/modules/intent_translator.py` | Natural language to constraints |
| **Modify** | `backend/modules/clinical.py` | Accept constraint filters |
| **Modify** | `backend/modules/synthesizer.py` | Accept constraints + rejected candidates |
| **Modify** | `backend/app.py` | `/chat`, `/reject-candidate`, `/session/{id}` endpoints + constraint-aware `run_pipeline` |
| **Modify** | `frontend/templates/index.html` | Add chat panel + agent feed UI |
| **Modify** | `frontend/static/js/main.js` | Chat state, constraint rendering, agent polling |
| **Modify** | `frontend/static/css/style.css` | Chat UI, candidate cards, activity feed styles |

---

## Architecture Decision Points

### Session storage
- **Recommendation:** In-memory dict for hackathon demo. Lost on restart but zero dependencies and fastest to implement.
- Upgrade path: Swap to SQLite later with no API changes.

### Agent status feed
- **Recommendation:** Simple polling (`GET /session/{id}` every 1.5s during activity). No WebSockets or SSE complexity.
- Simpler to implement, works with existing Flask setup, sufficient for demo fluidity.

### Constraint propagation
- Constraints accumulate in session state and are passed to `run_pipeline` as a `constraints` dict.
- Rejected candidates are tracked separately to ensure they never appear in subsequent results.

---

## Implementation Order

1. **Conversation state module** — session memory, data structures
2. **Intent translator** — parse intent, return constraints/clarifications
3. **`/chat` endpoint + constraint-aware pipeline** — wire translator to re-analysis
4. **Chat UI** — message bubbles, candidate cards, reject buttons
5. **Agent activity feed** — backend status + frontend polling
6. **Proactive clarification** — ambiguous feedback handling
7. **Polish** — constraint pills, steering buttons, animations
