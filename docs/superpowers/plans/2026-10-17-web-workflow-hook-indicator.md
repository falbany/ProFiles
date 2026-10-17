# Web Workflow Hook Integration and Indicator Implementation Plan

> **For implementer:** Follow each task in order using TDD. Do not skip verification commands. Make a git commit per task.

**Goal:** Integrate launch workflows with the web backend (`/api/actions/launch`), expose hook metadata (`has_hook`, `hook_pattern`) in `/api/scan/results`, and display a hook icon (`Webhook`) in the `#` index column of `FileListTable.tsx`.

---

## File Structure & Responsibilities

| File | Responsibility |
|---|---|
| `src/profiles/server/routes/actions.py` | Pass `config=state.config` and optional `logger` to `actions.launch_selected_file`. |
| `src/profiles/server/routes/scan.py` | Evaluate matching hook pattern via `select_most_specific_pattern` for each item in the paginated results slice and include `has_hook` and `hook_pattern`. |
| `tests/server/test_routes_actions.py` | Unit tests verifying `/api/actions/launch` forwards `config` and handles hook outcomes (`SUCCESS`, `FAILED`). |
| `tests/server/test_routes_scan.py` | Unit tests verifying `/api/scan/results` computes `has_hook` and `hook_pattern` correctly based on configured `launch_hooks`. |
| `src/profiles/web/src/api/types.ts` | Add `has_hook?: boolean` and `hook_pattern?: string \| null` to `ScannedFileItem`. |
| `src/profiles/web/src/components/FileListTable.tsx` | Render `Webhook` icon in the `#` index column next to the row index with tooltip and accessibility attributes when `file.has_hook` is true. |

---

## Tasks

### Task 1: Forward AppConfig to Launch Action in Web Server Route

**Files:**
- Modify: `tests/server/test_routes_actions.py`
- Modify: `src/profiles/server/routes/actions.py`

- [ ] **Step 1: Write failing test in `tests/server/test_routes_actions.py`**

Add `test_launch_forwards_config_and_handles_launch_hook`:
```python
@pytest.mark.anyio
async def test_launch_forwards_config_and_handles_launch_hook(
    test_state: ServerState, tmp_path: Path
) -> None:
    target = tmp_path / "sample.mttl"
    target.write_text("sample")
    test_state.config.launch_hooks = {"*.mttl": ()}
    expected = ActionResult(status=ActionStatus.SUCCESS, message="Launched with hook", path=target)
    app = create_app(test_state)

    with patch(
        "profiles.server.routes.actions.actions.launch_selected_file", return_value=expected
    ) as mock_launch:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/actions/launch",
                json={"directory": str(tmp_path), "filename": "sample.mttl"},
            )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_launch.assert_called_once()
    _, kwargs = mock_launch.call_args
    assert kwargs.get("config") is test_state.config
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_routes_actions.py -k test_launch_forwards_config_and_handles_launch_hook -v`
Expected: FAIL (kwargs does not contain `config` or `mock_launch` called without `config=test_state.config`)

- [ ] **Step 3: Update `launch_file` in `src/profiles/server/routes/actions.py`**

Inject `request: Request` into `launch_file`, extract `state = request.app.state.server_state`, and pass `config=state.config`:
```python
@router.post("/launch")
async def launch_file(payload: LaunchRequest, request: Request) -> dict:
    """Launch selected program via OS association and workflow actions."""
    state = request.app.state.server_state
    res = actions.launch_selected_file(
        directory=payload.directory,
        filename=payload.filename,
        release=payload.release,
        username=get_username(),
        args=payload.args,
        config=state.config,
    )
    if res.status != actions.ActionStatus.SUCCESS:
        raise HTTPException(status_code=400, detail=res.message)
    return {
        "status": str(res.status.value) if hasattr(res.status, "value") else str(res.status),
        "message": res.message,
        "path": str(res.path) if res.path else None,
    }
```
Ensure `Request` is imported from `fastapi`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_routes_actions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/routes/actions.py tests/server/test_routes_actions.py
git commit -m "feat(server): forward AppConfig to launch_selected_file for hook execution"
```

---

### Task 2: Compute and Expose Hook Metadata in Scan Results Endpoint

**Files:**
- Modify: `tests/server/test_routes_scan.py`
- Modify: `src/profiles/server/routes/scan.py`

- [ ] **Step 1: Write failing test in `tests/server/test_routes_scan.py`**

Add `test_scan_results_includes_hook_metadata`:
```python
@pytest.mark.anyio
async def test_scan_results_includes_hook_metadata(test_state: ServerState) -> None:
    # Configure a hook for .mttl files
    test_state.config.launch_hooks = {"*.mttl": ()}
    app = create_app(test_state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/scan",
            json={"extension": ".mttl", "filter_text": "", "recursive": True},
        )
        get_resp = await client.get("/api/scan/results")
        assert get_resp.status_code == 200
        items = get_resp.json()["items"]
        assert len(items) >= 1
        assert items[0]["has_hook"] is True
        assert items[0]["hook_pattern"] == "*.mttl"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/server/test_routes_scan.py -k test_scan_results_includes_hook_metadata -v`
Expected: FAIL (`KeyError: 'has_hook'`)

- [ ] **Step 3: Update `src/profiles/server/routes/scan.py`**

Import `select_most_specific_pattern`:
```python
from profiles.core.environment.matcher import select_most_specific_pattern
```

In `get_scan_results`, query `state.config.launch_hooks`:
```python
    hook_patterns = list(state.config.launch_hooks.keys()) if state.config.launch_hooks else []

    items = []
    for r in page:
        path_obj = getattr(r, "path", None)
        col_vals = getattr(r, "column_values", None) or {}
        fn = Path(path_obj).name if path_obj else _row_filename(r)
        matched_hook = select_most_specific_pattern(hook_patterns, fn) if hook_patterns else None
        items.append(
            {
                "filename": fn,
                "path": str(path_obj) if path_obj else "",
                "column_values": col_vals,
                "rel_path": getattr(r, "rel_path", ""),
                "has_hook": bool(matched_hook),
                "hook_pattern": matched_hook,
            }
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/server/test_routes_scan.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/profiles/server/routes/scan.py tests/server/test_routes_scan.py
git commit -m "feat(server): expose has_hook and hook_pattern in scan results"
```

---

### Task 3: Update TypeScript Types for ScannedFileItem

**Files:**
- Modify: `src/profiles/web/src/api/types.ts`

- [ ] **Step 1: Add hook properties to `ScannedFileItem` in `src/profiles/web/src/api/types.ts`**

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

- [ ] **Step 2: Verify type check passes**

Run: `cd src/profiles/web && npm run build`
Expected: PASS (`tsc -b && vite build` succeeds)

- [ ] **Step 3: Commit**

```bash
git add src/profiles/web/src/api/types.ts
git commit -m "feat(web): add has_hook and hook_pattern to ScannedFileItem type"
```

---

### Task 4: Add Hook Indicator to `FileListTable.tsx` Index Column

**Files:**
- Modify: `src/profiles/web/src/components/FileListTable.tsx`

- [ ] **Step 1: Import `Webhook` icon from `lucide-react` in `src/profiles/web/src/components/FileListTable.tsx`**

Update the imports:
```typescript
import { ArrowDown, ArrowLeftRight, ArrowUp, ArrowUpDown, FileCode, Loader2, Webhook } from "lucide-react";
```

- [ ] **Step 2: Update the `#` index column row rendering in `FileListTable.tsx`**

Replace:
```tsx
<div className="px-3 text-right font-mono text-ink-faint">
  <span className="hidden sm:inline">{idx + 1}</span>
</div>
```
With:
```tsx
<div className="flex items-center justify-end gap-1 px-3 font-mono text-ink-faint">
  {file.has_hook && (
    <span
      title={file.hook_pattern ? `Launch workflow: ${file.hook_pattern}` : "Launch workflow configured"}
      aria-label="Workflow hook attached"
      className="inline-flex items-center text-amber-500/80 hover:text-amber-400"
    >
      <Webhook className="h-3 w-3 shrink-0" />
    </span>
  )}
  <span className="hidden sm:inline">{idx + 1}</span>
</div>
```

- [ ] **Step 3: Verify TypeScript and Vite build**

Run: `cd src/profiles/web && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/profiles/web/src/components/FileListTable.tsx
git commit -m "feat(web): display hook icon in index column for files with launch workflows"
```

---

### Task 5: End-to-End Verification and Clean Build

**Files:**
- Test all changes together

- [ ] **Step 1: Run complete backend pytest suite**

Run: `pytest tests/server/ -v`
Expected: All tests pass

- [ ] **Step 2: Run frontend build**

Run: `cd src/profiles/web && npm run build`
Expected: Clean build with zero errors

- [ ] **Step 3: Run git status check**

Verify clean working directory with all tasks committed.
