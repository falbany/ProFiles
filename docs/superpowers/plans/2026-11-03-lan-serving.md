# LAN Serving Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--host` (default `0.0.0.0`) to the ProFiles CLI and a status-bar LAN on/off switch backed by a runtime rebind endpoint.

**Architecture:** The CLI resolves a bind host that flows through `ProFileApp` into `BackgroundServer` (desktop) for both GUI and `--server-only` modes. The running server registers itself on the FastAPI `app.state`; routes expose bind state and rebind through a structural `BindableServer` Protocol to avoid a server→desktop layering inversion. The frontend reflects/commands that state from the StatusBar identity pill.

**Tech Stack:** Python 3.11+/FastAPI/uvicorn/socket; React + TypeScript (vitest + @testing-library/react).

**Spec:** `docs/superpowers/specs/2026-11-03-lan-serving-design.md`

## Global Constraints

- `from __future__ import annotations` at the top of every modified Python file.
- Type hints on every public signature; no `Any`, no `# type: ignore` (tests/AGENTS.md).
- Bind values allowed: `"0.0.0.0"`, `"127.0.0.1"`, or a literal IPv4 address (no hostnames, no IPv6).
- Prefer `uv run pytest`, `uv run ruff check`, `uv run pylint` exactly as the repo Makefile does.
- Frontend tests run in `src/profiles/web` with `npx vitest run`.
- Test files mirror the package tree 1:1; every new directory needs `__init__.py`; update `tests/AGENTS.md` tree and `tests/README.md` when adding test files.
- The suite gate is 85% coverage (`--cov-fail-under=85`).

## Review Focus

The five conditions the review must not miss, each pinned by its owning task:

1. **Rebind while a UI client is connected** — the operator expects the open page (and any queued work) to keep working after LAN flips on; test: `tests/desktop/test_lifecycle.py::test_rebind_changes_host_and_reverses` re-issuing `GET /api/health` after `rebind`.
2. **Rebind failure (bind denied)** — the user expects the app still reachable at the original address, not dead; test: `tests/desktop/test_lifecycle.py::test_rebind_failure_reverts`.
3. **Invalid `--host` value** (e.g. `--host st-465`) — the user expects a clean argparse error and non-zero exit, not a traceback mid-launch; test: `tests/test_app_host.py::test_main_rejects_hostname`. Same review line covers `--host ::1` (IPv6): `tests/test_app_host.py::test_main_rejects_ipv6`.
4. **`GET /api/system` when no background server is registered** (test harness / static app factory) — `lan_enabled` must be `null` and the UI must hide/disable the toggle, not crash; test: `tests/server/routes/test_system.py::test_system_info_reports_unknown_bind_state`.
5. **PyWebView window URL on `0.0.0.0` bind** — the user expects the window to open (loopback URL), never `http://0.0.0.0:port`; test: `tests/desktop/test_launcher.py::test_webview_url_uses_loopback_for_wildcard_bind`.

---

### Task 1: `--host` CLI option (default `0.0.0.0`)

**Files:**
- Modify: `src/profiles/app.py` (parser ~570–650, `ProFileApp.__init__` ~91–109, `_run_web_gui` 308–338, `_run_server_only` 262–292)
- Test: `tests/test_app_host.py` (new)
- Modify: `tests/test_app_backend_selection.py:32-37` (default-host assertion flips)

**Interfaces:**
- Consumes: existing `main()` → `ProFileApp(...)` wiring (app.py:642–649).
- Produces:
  - `host_error(value: str) -> str | None` — module-level pure function; `None` when valid, else a human message (`"unsupported host '{value}' — use 0.0.0.0, 127.0.0.1, or an IPv4 address"`).
  - `ProFileApp(config_path, headless, server_only, no_config_propose, gui_backend, host: str = "0.0.0.0")` — stores `self._host`.
  - `_run_web_gui()` → calls `launch_desktop_window(self._config, port=<port>, host=self._host)`.
  - `_run_server_only()` → `BackgroundServer(config=self._config, host=self._host, port=<port>)`.
  - `main()` accepts `--host` (default `"0.0.0.0"`), validates via `host_error`, passes `host=args.host`.

- [ ] **Step 1: Write the failing tests** in `tests/test_app_host.py`:

```python
def test_host_error_accepts_wildcard_loopback_and_ipv4() -> None:
    assert host_error("0.0.0.0") is None
    assert host_error("127.0.0.1") is None
    assert host_error("172.16.41.65") is None


def test_host_error_rejects_hostname_and_ipv6() -> None:
    assert host_error("st-465") is not None
    assert host_error("::1") is not None


def test_default_host_is_lan_wildcard() -> None:
    app = ProFileApp(headless=False)
    assert app._host == "0.0.0.0"


def test_explicit_loopback_host_is_kept() -> None:
    app = ProFileApp(headless=False, host="127.0.0.1")
    assert app._host == "127.0.0.1"


def test_main_rejects_hostname() -> None:
    with patch.object(sys, "argv", ["profiles", "--host", "st-465"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
    assert excinfo.value.code == 2


def test_main_rejects_ipv6() -> None:
    with patch.object(sys, "argv", ["profiles", "--host", "::1"]):
        with pytest.raises(SystemExit) as excinfo:
            main()
    assert excinfo.value.code == 2


def test_main_passes_host_argument(mut: unittest.mock.MagicMock) -> None:
    # mirror _resolved_backend() pattern from tests/test_app_backend_selection.py:
    # patch profiles.app.ProFileApp, assert call.kwargs["host"] == "127.0.0.1"
```

- [ ] **Step 2: Run and verify failure** — `uv run pytest tests/test_app_host.py -v`. Expected: import error / all FAIL ("host_error", `--host` not defined yet).
- [ ] **Step 3: Implement** — add `host_error()` (validate with `ipaddress.ip_address`; require `.version == 4`; `"0.0.0.0"`/`"127.0.0.1"` are ordinary IPv4 literals), add `--host` argparse argument with `help` mentioning the default, post-parse: `error = host_error(args.host); parser.error(error)` when not None (argparse exit code is 2), add `host: str = "0.0.0.0"` to `ProFileApp.__init__` (store `self._host`), make `_run_web_gui()`/`_run_server_only()` use `self._host` instead of their loopback/wildcard literal defaults, pass `host=args.host` in the `ProFileApp` construction at main(), and append this line to the epilog examples block after the existing server-only example line:
  `  profiles --host 127.0.0.1                 Restrict serving to this machine (loopback only)`
- [ ] **Step 4: Update the superseded assertion** in `tests/test_app_backend_selection.py:37`: `mock_launch.assert_called_once_with(app._config, port=8088, host="0.0.0.0")`.
- [ ] **Step 5: Run** — `uv run pytest tests/test_app_host.py tests/test_app_backend_selection.py -v`. Expected: PASS. Run `uv run pytest -q` and see the whole suite green.
- [ ] **Step 6: Lint** — `uv run ruff check src/profiles/app.py tests/test_app_host.py && uv run ruff format src/profiles/app.py tests/test_app_host.py`.
- [ ] **Step 7: Update test docs** — add `test_app_host.py` to the `tests/AGENTS.md` tree and `tests/README.md`.
- [ ] **Step 8: Commit** — `git add src/profiles/app.py tests/test_app_host.py tests/test_app_backend_selection.py tests/AGENTS.md tests/README.md` then `git commit -m "feat: add --host CLI option (default 0.0.0.0, LAN serving)"`.

### Task 2: Connectable window URL + URL banner for GUI launches

**Files:**
- Modify: `src/profiles/desktop/launcher.py` (`launch_desktop_window` 63–89)
- Test: `tests/desktop/test_launcher.py` (new; also creates `tests/desktop/__init__.py` already exists — keep)

**Interfaces:**
- Consumes: `BackgroundServer.start()` (unchanged), `profiles.utils.network.get_local_ip()`.
- Produces: `launch_desktop_window(config, port, host, debug)` behavior:
  - window URL is `http://127.0.0.1:{server.port}` when `host == "0.0.0.0"`, else `http://{host}:{server.port}`;
  - after a successful `server.start()` it prints, when `host == "0.0.0.0"`:
    ```
    ProFiles web GUI running at:
      Local:   http://127.0.0.1:{port}
      Network: http://{get_local_ip()}:{port}
    ```
    and when bound to anything else, prints a single `Local:   http://{host}:{port}` line (no Network line).

- [ ] **Step 1: Write the failing tests** in `tests/desktop/test_launcher.py` (mock the whole `webview` module with `unittest.mock.MagicMock` via `patch.dict(sys.modules)` so no window system is touched, and patch `profiles.utils.network.get_local_ip`):

```python
def test_webview_url_uses_loopback_for_wildcard_bind(...) -> None:
    # launch_desktop_window(AppConfig(title="t"), port=find_available_port(8000), host="0.0.0.0")
    # assert mocked webview.create_window called with url startswith "http://127.0.0.1:"
    # assert capsys captured "Network:" line

def test_webview_url_and_single_line_for_loopback_bind(...) -> None:
    # same but host="127.0.0.1": url startswith "http://127.0.0.1:", capsys has exactly one
    # "Local:" line and no "Network:" line
```

- [ ] **Step 2: Run** — `uv run pytest tests/desktop/test_launcher.py -v`. Expected: FAIL (no banner printed).
- [ ] **Step 3: Implement** in `launch_desktop_window` — compute `webview_url` per the rule above for `webview.create_window(url=...)`; print the banner after a successful `server.start()` per the rule above; keep the existing `ServerStartError` propagation untouched.
- [ ] **Step 4: Run** — `uv run pytest tests/desktop -v`. Expected: PASS (old lifecycle tests still green).
- [ ] **Step 5: Lint** + update `tests/AGENTS.md` (remove `launcher.py` from "Known coverage gaps") and `tests/README.md`.
- [ ] **Step 6: Commit** — `git commit -m "feat: connectable PyWebView URL and URL banner for LAN bind"`.

### Task 3: `BackgroundServer.rebind` with revert-on-failure

**Files:**
- Modify: `src/profiles/desktop/lifecycle.py` (register app state in `start()` ~123–157; add `rebind` after `stop()` ~206–218)
- Test: `tests/desktop/test_lifecycle.py` (extend)

**Interfaces:**
- Consumes: existing `start()`, `stop()`, `is_running`, `self.host`, `self._app`.
- Produces:
  - `rebind(self, host: str) -> None` — public method on `BackgroundServer`:
    - returns without side effects when `host == self.host and self.is_running`;
    - otherwise `stop()`, set `self.host = host`, `start()`;
    - on `ServerStartError`: restore `self.host` to the previous host, `start()` again (the server is back serving the original address), then re-raise the original `ServerStartError`.
  - `start()` sets `self._app.state.background_server = self` right after `_bind_listener()` succeeds (so later tasks can find the server from route code).

- [ ] **Step 1: Write the failing tests** in `tests/desktop/test_lifecycle.py`:

```python
def test_rebind_changes_host_and_reverses() -> None:
    port = find_available_port(start_port=8000)
    server = BackgroundServer(config=AppConfig(title="rebind"), host="127.0.0.1", port=port)
    server.start()
    try:
        server.rebind("0.0.0.0")
        assert server.host == "0.0.0.0"
        response = httpx.get(f"http://127.0.0.1:{port}/api/health")
        assert response.status_code == 200
        # app.state registration the next task relies on:
        assert server._app.state.background_server is server
    finally:
        server.stop()


def test_rebind_failure_reverts(mocker) -> None:
    mocker.patch(
        "socket.socket.bind",
        lambda sock, addr: _raise_or_delegate(
            sock, addr
        ),  # OSError when addr[0] == "0.0.0.0"; real bind otherwise — capture socket.socket.bind BEFORE patching
    )
    port = find_available_port(start_port=8000)
    server = BackgroundServer(config=AppConfig(title="revert"), host="127.0.0.1", port=port)
    server.start()
    try:
        with pytest.raises(ServerStartError):
            server.rebind("0.0.0.0")
        assert server.host == "127.0.0.1"
        assert server.is_running
        assert httpx.get(f"http://127.0.0.1:{port}/api/health").status_code == 200
    finally:
        server.stop()
```

(The `_raise_or_delegate` helper must hold the real `socket.socket.bind` captured before `mocker.patch`, then call it for non-wildcard addresses — see tests/AGENTS.md "What to Mock": `socket.socket`.)

- [ ] **Step 2: Run** — `uv run pytest tests/desktop/test_lifecycle.py -v`. Expected: FAIL (`AttributeError: rebind`).
- [ ] **Step 3: Implement** `rebind` exactly per the Produces contract above (docstring states the revert contract); add the `self._app.state.background_server = self` line in `start()`.
- [ ] **Step 4: Run** — `uv run pytest tests/desktop -v`. Expected: PASS.
- [ ] **Step 5: Lint** — `uv run ruff check src/profiles/desktop/lifecycle.py && uv run pylint src/profiles/desktop --fail-under=8.0`.
- [ ] **Step 6: Commit** — `git commit -m "feat: BackgroundServer.rebind with revert-on-failure"`.

### Task 4: `/api/system` bind status + `POST /api/system/bind`

**Files:**
- Modify: `src/profiles/server/state.py` (add Protocol)
- Modify: `src/profiles/server/routes/system.py` (both routes; request model)
- Test: `tests/server/routes/test_system.py` (extend)

**Interfaces:**
- Consumes: `app.state.background_server: BindableServer | None` from Task 3; `ServerStartError` (function-level import from `profiles.desktop.lifecycle` inside the route's except — module-level import would create a server↔desktop import cycle).
- Produces:
  - In `state.py`: `class BindableServer(Protocol)` with `host: str`, `@property is_running -> bool`, `def rebind(self, host: str) -> None`.
  - `GET /api/system` response adds `"lan_enabled": bool | None` — `None` when no server registered, else `server.host == "0.0.0.0"`.
  - `POST /api/system/bind` — pydantic request model `BindRequest(lan: bool)`; returns `{"host": str, "lan_enabled": bool}` on success; `HTTPException(503, "no running server to rebind")` when no `background_server`; `HTTPException(500, str(exc))` on `ServerStartError` (state is left on the original bind by Task 3's revert).

- [ ] **Step 1: Write the failing tests** in `tests/server/routes/test_system.py` (existing `AsyncClient` + `create_app` pattern):

```python
def test_system_info_reports_unknown_bind_state(test_state) -> None:
    # GET /api/system → data["lan_enabled"] is None

def test_bind_without_server_returns_503(test_state) -> None:
    # POST /api/system/bind {"lan": true} → 503

def test_bind_runs_rebind_on_registered_server(test_state, mocker) -> None:
    # app = create_app(test_state)
    # stub: class implementing BindableServer with rebind recording the host and updating .host
    # app.state.background_server = stub
    # POST {"lan": true} → 200 {"host": "0.0.0.0", "lan_enabled": True}

def test_bind_failure_returns_500_and_state_is_unchanged(test_state) -> None:
    # stub whose rebind raises ServerStartError (function-level import in test is fine)
    # POST {"lan": true} → 500, detail contains the message
    # stub.host still "127.0.0.1"; GET /api/system → lan_enabled False
```

- [ ] **Step 2: Run** — `uv run pytest tests/server/routes/test_system.py -v`. Expected: FAIL (`lan_enabled` missing / 404 on bind).
- [ ] **Step 3: Implement** — `BindableServer` Protocol in `state.py`; rework `system_info(request)` to add the field; add `BindRequest` + `bind_route` (see signatures above; use `getattr(request.app.state, "background_server", None)` typed as `BindableServer | None`).
- [ ] **Step 4: Run** — `uv run pytest tests/server/routes/test_system.py -v`. Expected: PASS. Then `uv run pytest tests/server -v`. Expected: PASS (no route regression).
- [ ] **Step 5: Lint** — ruff + `uv run pylint src/profiles/server --fail-under=8.0`.
- [ ] **Step 6: Commit** — `git commit -m "feat: system bind-status endpoint and LAN rebind API"`.

### Task 5: Frontend — LAN switch in the status bar

**Files:**
- Modify: `src/profiles/web/src/api/types.ts:1-6` (`SystemInfo` gains `lan_enabled: boolean | null;`)
- Modify: `src/profiles/web/src/api/client.ts` (new export after `fetchSystemInfo`)
- Modify: `src/profiles/web/src/components/StatusBar.tsx` (identity pill; props)
- Modify: `src/profiles/web/src/App.tsx` (state, handler, ConfirmDialog + showToast)
- Test: `src/profiles/web/src/components/StatusBar.test.tsx` (new)

**Interfaces:**
- Consumes: `GET /api/system` → `lan_enabled: boolean | null`; `POST /api/system/bind` (Task 4); `ConfirmDialog` props `{isOpen, title, message, confirmLabel, onConfirm, onCancel}`; App's `showToast(message, kind)`; App's existing systemInfo refetch blocks (App.tsx:300, 586).
- Produces:
  - `setLanEnabled(lan: boolean): Promise<{ host: string; lan_enabled: boolean }>` in `client.ts` (POST `/api/system/bind`; on `!res.ok` read `detail` from the JSON body and throw `new Error(detail)` — mirroring `apiError`'s preference).
  - `StatusBarProps` gains `lanEnabled?: boolean | null` and `onToggleLan?: (next: boolean) => void`; the pill renders a LAN toggle *only* when `onToggleLan` is provided: an `aria-pressed` icon-button (lucide `Network` icon + `LAN` label) with `Tooltip "LAN access"`; disabled and non-interactive when `lanEnabled === null`; visually on when `lanEnabled === true` (success color), muted otherwise.
  - App wiring: clicking the switch opens an in-app `ConfirmDialog` (never `window.confirm` — webview no-op, issue #31):
    - enabling — title `"Enable LAN access?"`, message `ProFiles will be reachable by anyone on this network:\nhttp://{hostname}:{port}\nhttp://{ip}:{port}`, confirmLabel `"Enable LAN"`;
    - disabling — title `"Restrict to this machine?"`, message `ProFiles will be reachable only on this machine.`, confirmLabel `"Restrict"`;
    - on confirm: `setLanEnabled(next)` → refetch `fetchSystemInfo()` → `showToast(next ? "ProFiles is now reachable on the local network." : "ProFiles is restricted to this machine.")` ("info");
    - on error: `showToast("Failed to update LAN binding: <message>", "error")` — never change the toggle state on failure (refetch decides it).

- [ ] **Step 1: Write the failing component test** (`StatusBar.test.tsx`, mirroring `WorkflowRunnerModal.test.tsx`'s vitest + @testing-library conventions):

```tsx
// render StatusBar with systemInfo={…}, lanEnabled={false}, onToggleLan={spy}
// → a button (accessible name contains "LAN") exists and is not disabled; click calls onToggleLan(true) (next=false → spy(true))
// render with lanEnabled={true} → button has aria-pressed="true"
// render with lanEnabled={null} → button is disabled
// render without onToggleLan → no LAN button at all
```

- [ ] **Step 2: Run** — in `src/profiles/web`: `npx vitest run src/components/StatusBar.test.tsx`. Expected: FAIL (no LAN button).
- [ ] **Step 3: Implement** — widen `SystemInfo`, add `setLanEnabled` to `client.ts`, add the two props + toggle to `StatusBar.tsx` (place the toggle inside the identity pill, after the username segment, separated by the existing `|` divider style).
- [ ] **Step 4: Wire App.tsx** — `lanPending` state + `toggleLan(next)` handler + one more `<ConfirmDialog>` next to the existing ones; pass `lanEnabled={systemInfo ? systemInfo.lan_enabled : null}` and `onToggleLan={toggleLan}` to `<StatusBar>`; also update the two existing `fetchSystemInfo` sites if their consumers need nothing new (they store the whole object — verify no type breakage).
- [ ] **Step 5: Run** — `npx vitest run`. Expected: PASS (all frontend tests).
- [ ] **Step 6: Commit** — `git commit -m "feat(web): LAN binding toggle in the status bar"`.

### Task 6: Rebuild frontend, full verification, docs

**Files:**
- Modify: `src/profiles/web/dist/**` (regenerated build artifacts, per the existing web-build convention)
- Possibly verify: `README*` / `docs/` CLI mentions — if and only if a CLI examples section exists, add the same `--host` line as the argparse epilog.

**Interfaces:**
- Consumes: everything from Tasks 1–5.
- Produces: a rebuilt `web/dist` so the served PWA carries the new UI; a full green verification record.

- [ ] **Step 1: Rebuild the web frontend** — `uv run python src/profiles/web/build.py` (or the repo's established build entry). Verify `src/profiles/web/dist/assets/*.js` contains the string `api/system/bind`.
- [ ] **Step 2: Full Python verification** — `uv run ruff check .`, `uv run ruff format --check .`, `uv run pylint src/profiles --fail-under=8.0`, `uv run pytest --cov` (green, ≥85%).
- [ ] **Step 3: Docs check** — `grep -rn -- "--server-only" README* docs/ | head` — if a real CLI-examples section exists, add the `--host 127.0.0.1` loopback line next to what's documented and commit it; otherwise record "no CLI docs section found" and skip.
- [ ] **Step 4: Commit remaining changes** — `git add -A && git commit -m "build: rebuild web frontend for LAN toggle" -- docs (only if changed)`.
- [ ] **Step 5: Manual verification note for the partner** (not automatable here): launch `ProFiles`, confirm the banner in console, confirm `http://<hostname>:8088` loads from *another* machine or the same machine via IP, then check the LAN pill toggles and reverts on failure.
