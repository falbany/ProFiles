# LAN Serving Design — `--host` CLI + Status-bar LAN toggle

**Date:** 2026-11-03
**Status:** Approved (conversation: design for `--host` approved, then UI toggle
approved with build order "CLI first, then the pill toggle").

## Intent

Let any machine on the local network open `http://<hostname>:8088/` right after
a normal `ProFiles` launch, while keeping a one-flag way to stay loopback-only —
and let the station operator flip that access at runtime from the web UI.

## Goals

- `ProFiles` (GUI, default) serves on `0.0.0.0` by default — LAN reachable.
- `--host` CLI option shared by GUI (desktop window) and `--server-only` mode.
- `--host 127.0.0.1` restores the old loopback-only behavior.
- The PyWebView window always opens on a connectable URL (`127.0.0.1` when the
  bind host is `0.0.0.0`).
- Console shows `Local:` and `Network:` URLs on GUI launches too.
- StatusBar identity pill gains a LAN on/off switch (transient — not persisted
  across restarts) with a in-app confirmation naming the exposed URLs.
- Runtime rebind reverts the bind on failure; the app must never end up dead.

## Non-goals

- No persistence of the runtime LAN choice (restart = launch default).
- No IPv6 binding and no hostname bind values (socket stays IPv4; see
  `lifecycle.py` `_bind_listener` constraint comment).

## Decisions (as made with the human partner)

- Build order: (1) CLI, (2) status-bar toggle on top of the same rebind path.
- Accepted bind values: `0.0.0.0`, `127.0.0.1`, or a literal IPv4 address.
  Hostnames and IPv6 literals are rejected with an argparse error.
- Toggle state comes from `GET /api/system` (`lan_enabled`), changes via
  `POST /api/system/bind` (`{"lan": bool}`). A confirm dialog mentions the
  exposed hostname/IP URLs. Failure surfaces a toast; state stays unchanged.
- UI-first caveat acknowledged: a colleague on another machine cannot toggle
  LAN on a loopback-bound app (they can't open the UI) — that is why the CLI
  default matters more.

## Constraints

- Layering: `server/` must not import `profiles.desktop.*` at module level
  (desktop imports server). Route access to the running server cross-layer
  goes through a structural Protocol (`BindableServer`) in `server/state.py`,
  registered on `app.state` by `BackgroundServer.start()`.
- `window.confirm`/`window.alert` are no-ops inside webviews — the project
  uses in-app `ConfirmDialog` and `showToast`.
- Test suite mirrors package tree 1:1; suite gate 85% coverage.
