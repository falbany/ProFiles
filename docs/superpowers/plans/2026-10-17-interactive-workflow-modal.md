# Interactive Launch Workflow Modal Implementation Plan

> **For implementer:** Follow each task in order using TDD. Do not skip verification commands. Make a git commit per task.

**Goal:** Implement interactive workflow runner modal (`WorkflowRunnerModal.tsx`), supporting live step progression, `ask` prompts (Yes / Skip / No), `notify` dialogs, and backend interactive stepping session API.

---

## Architecture Overview

```
Frontend (WorkflowRunnerModal)
   │
   ├─► POST /api/workflow/start { directory, filename } ──► Returns session_id, matched_pattern, steps
   │
   ├─► GET /api/workflow/{session_id}/status ──► Returns current_step, step_status, prompt (ask/notify)
   │
   ├─► POST /api/workflow/{session_id}/respond { action: "yes" | "skip" | "no" | "ack" }
   │
   └─► Auto-proceed / Complete ──► Final launch or skip notification
```

---

## Tasks

### Task 1: Backend Interactive Workflow Session Engine & Router

**Files:**
- Create: `src/profiles/server/routes/workflow.py`
- Modify: `src/profiles/server/app.py`
- Test: `tests/server/test_routes_workflow.py`

- [ ] **Step 1: Write failing test in `tests/server/test_routes_workflow.py`**
Verify starting a session returns steps, and answering `ask` or `notify` advances the workflow.

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/server/test_routes_workflow.py -v`
Expected: FAIL (module/routes not found)

- [ ] **Step 3: Implement `src/profiles/server/routes/workflow.py`**
Create endpoints:
- `POST /api/workflow/start`: validates file and pattern, instantiates interactive session with steps.
- `GET /api/workflow/{session_id}`: returns state (`waiting_ask`, `waiting_notify`, `running`, `completed`, `aborted`, `error`).
- `POST /api/workflow/{session_id}/respond`: accepts response to `ask` or acknowledgement for `notify`.
Mount in `src/profiles/server/app.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/server/test_routes_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/profiles/server/routes/workflow.py src/profiles/server/app.py tests/server/test_routes_workflow.py
git commit -m "feat(server): add interactive workflow runner API endpoints"
```

---

### Task 2: Frontend Workflow API Client & Types

**Files:**
- Modify: `src/profiles/web/src/api/types.ts`
- Modify: `src/profiles/web/src/api/client.ts`

- [ ] **Step 1: Add types for workflow session and step status**
Define:
- `WorkflowSession`: `id`, `filename`, `pattern`, `steps`, `status`, `current_step_index`, `ask_prompt`, `notify_message`.
- `WorkflowStepItem`: `action`, `content`, `ask`, `status`.

- [ ] **Step 2: Add client methods in `client.ts`**
- `startWorkflow(directory, filename)`
- `getWorkflowStatus(sessionId)`
- `respondWorkflow(sessionId, choice)`

- [ ] **Step 3: Verify TypeScript builds**
Run: `cd src/profiles/web && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add src/profiles/web/src/api/types.ts src/profiles/web/src/api/client.ts
git commit -m "feat(web): add workflow session types and api client methods"
```

---

### Task 3: Build `WorkflowRunnerModal.tsx` Component

**Files:**
- Create: `src/profiles/web/src/components/WorkflowRunnerModal.tsx`

- [ ] **Step 1: Implement `WorkflowRunnerModal.tsx`**
- Step checklist with icons (`Loader2`, `CheckCircle2`, `SkipForward`, `AlertCircle`, `Workflow`).
- Prompt area for `ask` (`Yes`, `Skip`, `No`) and `notify` (`Continue`).
- Command & message output preview.
- Keyboard navigation (Esc to abort, Enter to confirm/continue).

- [ ] **Step 2: Verify component compiles**
Run: `cd src/profiles/web && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add src/profiles/web/src/components/WorkflowRunnerModal.tsx
git commit -m "feat(web): add WorkflowRunnerModal component with live step progression"
```

---

### Task 4: Integrate Workflow Modal into `App.tsx`

**Files:**
- Modify: `src/profiles/web/src/App.tsx`

- [ ] **Step 1: Connect launch trigger to `WorkflowRunnerModal`**
When `file.has_hook` is true on launch, open `WorkflowRunnerModal` instead of immediate fire-and-forget OS launch.
When file has no hook, proceed directly with standard `launchFile`.

- [ ] **Step 2: Run frontend build**
Run: `cd src/profiles/web && npm run build`
Expected: PASS

- [ ] **Step 3: Commit**
```bash
git add src/profiles/web/src/App.tsx
git commit -m "feat(web): launch hooked files through WorkflowRunnerModal"
```

---

### Task 5: End-to-End Verification

- [ ] **Step 1: Run all Python tests**
Run: `pytest tests/server/ -v`

- [ ] **Step 2: Run frontend build and python build script**
Run: `python3 src/profiles/web/build.py`
