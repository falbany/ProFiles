# Launch Workflows Integration and Indicator Design

## 🎯 Intent & Why
Launch workflows (hooks) execute customized sequences of steps (`run`, `run_after`, `replace`, `notify`, `check`) when files are launched.
In the desktop Tkinter UI, hooks run automatically before/during launch. In the web application:
1. The web backend launch route (`/api/actions/launch`) currently omits the loaded `AppConfig`, causing file launches from the web UI to bypass launch hooks entirely.
2. The user has no visual cue in the web UI table (`FileListTable.tsx`) to know whether double-clicking / launching a file will trigger an automated hook workflow versus standard OS association.
3. Marking files with a hook icon in the index column (`#`) gives immediate visibility and clarity before launching.
4. Setting up this hook metadata lays the groundwork for the upcoming dedicated interactive workflow modals in the web frontend.

---

## 🚀 Goals & Non-Goals

### Goals
- **Enable Web App Hook Execution**: Ensure `/api/actions/launch` forwards `config=state.config` to `actions.launch_selected_file`.
- **Expose Hook Matching Metadata**: Evaluate `select_most_specific_pattern` against `state.config.launch_hooks` for scanned files, returning `has_hook: bool` and optional `hook_pattern: str | null` in scan result items.
- **Visual Indicator in Index Column**: In `FileListTable.tsx`, display a hook icon (`Webhook`) inside the `#` index cell next to the row number when `file.has_hook` is true, complete with tooltip indicating the hook workflow is attached.
- **Testing & Verification**: Ensure backend tests cover hook dispatch in FastAPI and frontend builds cleanly (`npm run build`).

### Non-Goals
- Dedicated interactive workflow dialogs (e.g., custom web modal prompts for `ask` or rich `notify` modals) are the **next step** as requested. In headless / web server mode, default console/dialog primitives currently handle or skip prompts without blocking the event loop.

---

## 🛠️ Architecture & Changes

### 1. Backend (`src/profiles/server/routes/actions.py`)
- Pass `config=request.app.state.server_state.config` and `logger=request.app.state.server_state.logger` (or root logger) into `actions.launch_selected_file(...)`.
- Handle any launch outcomes (`FAILED`, `SUCCESS`) cleanly.

### 2. Backend (`src/profiles/server/routes/scan.py`)
- When serializing cached results into `/api/scan/results` response:
  - Check `state.config.launch_hooks`.
  - Use `select_most_specific_pattern(patterns, filename)` to detect if a hook applies.
  - Include `has_hook: bool` (and `hook_pattern: str | None`) in the serialized item dictionary.

### 3. Frontend Types (`src/profiles/web/src/api/types.ts`)
- Update `ScannedFileItem`:
  ```typescript
  export interface ScannedFileItem {
    filename: string;
    path: string;
    column_values: Record<string, string>;
    rel_path: string;
    has_hook?: boolean;
    hook_pattern?: string | null;
  }
  ```

### 4. Frontend Component (`src/profiles/web/src/components/FileListTable.tsx`)
- Import `Webhook` icon from `lucide-react`.
- In the index column cell (`#`):
  ```tsx
  <div className="flex items-center justify-end gap-1 px-2 font-mono text-ink-faint">
    {file.has_hook && (
      <Webhook
        className="h-3 w-3 text-indigo-400 shrink-0"
        title={file.hook_pattern ? `Workflow hook: ${file.hook_pattern}` : "Workflow hook configured"}
        aria-label="Workflow hook configured"
      />
    )}
    <span className="hidden sm:inline">{idx + 1}</span>
  </div>
  ```

---

## 🧪 Verification Plan
1. **FastAPI Route Tests**: Add/verify tests checking that `/api/scan/results` includes `has_hook: true` when `config.launch_hooks` matches.
2. **Launch Route Test**: Verify that `/api/actions/launch` passes `config` to `launch_selected_file`.
3. **Frontend Build**: Run `npm run build` in `src/profiles/web` to guarantee TypeScript types and bundle succeed.
4. **Pytest**: Run `pytest tests/server/` to ensure no regression.
