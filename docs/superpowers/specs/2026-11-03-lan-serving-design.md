# LAN Serving Design — `--host` CLI + Status-bar LAN toggle

**Date:** 2026-11-03
**Status:** Approved (conversation: design for `--host` approved, then UI toggle
approved with build order "CLI first, then the pill toggle").
**Revised 2026-11-03 (same day, after the toggle shipped):** default bind
flipped from `0.0.0.0` to `127.0.0.1` — see Decisions.

## Intent

Keep a fresh ProFiles launch **loopback-only**; let the station operator expose
the machine to the local network with one click from the web UI status bar (or
pre-expose it at launch with `--host 0.0.0.0`), and flip it back just as
easily.

## Goals

- `ProFiles` (GUI and `--server-only`) serves on `127.0.0.1` by default —
  loopback-only, nothing reachable from the network until the operator opts in.
- `--host` CLI option shared by GUI (desktop window) and `--server-only` mode;
  `--host 0.0.0.0` pre-enables LAN serving for headless/automation launches.
- The PyWebView window always opens on a connectable URL (`127.0.0.1` when the
  bind host is `0.0.0.0`).
- Console shows `Local:` and `Network:` URLs only when the bind actually
  exposes the network.
- StatusBar identity pill gains a LAN on/off switch (transient — not persisted
  across restarts) with an in-app confirmation naming the exposed URLs.
- Runtime rebind reverts the bind on failure; the app must never end up dead.

## Non-goals

- No persistence of the runtime LAN choice (restart = launch default, i.e.
  loopback-only again).
- No IPv6 binding and no hostname bind values (socket stays IPv4; see
  `lifecycle.py` `_bind_listener` constraint comment).

## Decisions (as made with the human partner)

- Build order: (1) CLI, (2) status-bar toggle on top of the same rebind path.
- Accepted bind values: `0.0.0.0`, `127.0.0.1`, or a literal IPv4 address.
  Hostnames and IPv6 literals are rejected with an argparse error.
- Toggle state comes from `GET /api/system` (`lan_enabled`), changes via
  `POST /api/system/bind` (`{"lan": bool}`). A confirm dialog mentions the
  exposed hostname/IP URLs. Failure surfaces a toast; state stays unchanged.
- **Revision (2026-11-03):** the launch default is `127.0.0.1`, reversing the
  original "serve `0.0.0.0` by default" decision. Rationale: the status-bar
  toggle makes LAN exposure a one-click opt-in at runtime, so serving the LAN
  by default is no longer justified — secure-by-default wins. `--host 0.0.0.0`
  remains available for headless/automation launches where nobody will click
  the toggle. The original caveat ("a colleague cannot toggle LAN on a
  loopback-bound app") is accepted: the operator toggles at the console.

## Constraints

- Layering: `server/` must not import `profiles.desktop.*` at module level
  (desktop imports server). Route access to the running server cross-layer
  goes through a structural Protocol (`BindableServer`) in `server/state.py`,
  registered on `app.state` by `BackgroundServer.start()`.
- `window.confirm`/`window.alert` are no-ops inside webviews — the project
  uses in-app `ConfirmDialog` and `showToast`.
- Test suite mirrors package tree 1:1; suite gate 85% coverage.
