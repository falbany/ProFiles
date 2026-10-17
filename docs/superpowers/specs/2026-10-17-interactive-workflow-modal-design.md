# Interactive Launch Workflows Modal Specification & Plan

## 🎯 Intent & Why
Launch workflows (hooks) consist of a series of steps (`run`, `run_after`, `replace`, `notify`, `check`) executed before or instead of launching a file.
Currently, when a file with a hook is double-clicked in the web UI, `/api/actions/launch` executes `run_workflow` on the backend, which falls back to console or standard headless prompts when user interactions (`ask` or `notify`) occur.

To give users full control and real-time visibility in the web application:
1. **Interactive Workflow Modal**: When a file with a hook (`has_hook: true`) is launched, an interactive Workflow Runner Modal opens in the web UI.
2. **Real-time Step Execution**: The backend streams or reports step-by-step progress, showing step type (`run`, `notify`, `check`, etc.), parameters, live status (`running`, `completed`, `skipped`, `failed`), and output/messages.
3. **Interactive Decisions (`ask`)**: When a step encounters an `ask` guard, the workflow modal pauses and presents **Yes**, **Skip**, and **No** (abort) buttons.
4. **Rich Notifications (`notify`)**: Formatted Markdown messages display clearly inside the modal with an **OK** / **Continue** button to acknowledge and proceed.
5. **Clear Final Outcome**: Once finished, the modal displays the final outcome badge (`CONTINUE` → file launched via OS, `SKIP_LAUNCH` → handled by workflow/replace, `ABORT` → cancelled by user/error) and closes or allows dismiss.

---

## 🚀 Key Requirements & Capabilities

### Backend
- **Workflow State & Interactive Endpoint (`/api/workflow`)**:
  - Add WebSocket or SSE / REST polling endpoint for active workflow execution sessions.
  - Expose a `run_workflow_interactive` engine or callback handler that receives web user inputs (`yes`, `skip`, `no`, `acknowledge`) for `ask` and `notify` steps via websocket/HTTP endpoints.

### Frontend
- **`WorkflowRunnerModal.tsx`**:
  - Dedicated component with header displaying target file name and active workflow pattern (e.g. `*.mttl`).
  - **Step Checklist**: List of workflow steps with icons (`run`, `notify`, `check`, `replace`, `run_after`), execution state spinners, timers, and logs/messages.
  - **Interactive Action Area**:
    - For `ask` steps: Prominent card with question text and **Yes**, **Skip**, **No** button group.
    - For `notify` steps: Rendered Markdown message box with **Continue** button.
    - For errors (`on_failure`): Detailed failure message and error resolution badge.
  - **Footer**: Cancel/Abort button, auto-close option on successful launch.

---

## 🏗️ Architecture & Component Design

### Workflow Session State (`src/profiles/server/routes/workflow.py`)
- Session object storing:
  - `session_id`: Unique launch run ID.
  - `file_path`, `steps`: Steps loaded from config matching pattern.
  - `current_step_index`: Current step being evaluated.
  - `status`: `pending`, `running`, `waiting_ask`, `waiting_notify`, `completed`, `aborted`.
  - `ask_prompt`: Current question for `ask` step.
  - `notify_content`: Current rendered Markdown for `notify` step.
  - `outcomes`: List of step results (`success`, `skipped`, `failed`).

---

## 🧪 Verification Plan
1. **Backend Tests (`tests/server/test_routes_workflow.py`)**:
   - Verify interactive workflow creation, stepping, `ask` decision dispatch (`yes`/`skip`/`no`), and final launch completion.
2. **Frontend Build & Integration (`npm run build`)**:
   - Build TypeScript and Vite package cleanly with `WorkflowRunnerModal.tsx`.
3. **End-to-End Simulation**:
   - Verify double-clicking a hooked file opens `WorkflowRunnerModal`, steps through `notify` and `ask` prompts, and updates table status.
