# Launch Hooks — Reference

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.en.md)** |
> ⚙️ **[Configuration](./configuration-profile.en.md)** |
> 🔧 **Hooks** |
> 📊 **[Dynamic Columns](./dynamic-columns-guide.md)** |
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

---

Launch hooks let you run arbitrary commands around every file launch. The pipeline lives in
`src/profiles/core/environment/execution.py` and is invoked by `launch_selected_file` in
`actions.py`. Hooks are configured per-extension in the `[HOOKS]` section of the
`.profiles` INI file.

## Overview

- **When** – before the OS association is executed, after it returns, or instead of it.
- **Phases** – `before`, `after`, `instead`, `abort`.
- **Outcome** – the pipeline returns a `HookOutcome` (`CONTINUE`, `SKIP`, `ABORT`).
- **Scope** – hooks apply to the normalized extension key (`.png`, `.pdf`, …).

The hook string may omit a phase; the default is `before`. Multiple hooks are comma‑
separated; commas inside double quotes are ignored.

## Quick Start

```ini
[HOOKS]
.mttl = before|echo "Launching {path}" , after|logger "Launched {path}"
```

- `before` prints a message, aborts on non‑zero exit according to `launch_hook_failmode`.
- `after` runs asynchronously after the OS launch.

## Hook Phases

| Phase    | When it runs                               | Return‑code handling                             |
| -------- | ------------------------------------------ | ------------------------------------------------ |
| before   | Immediately before the OS launch.          | `0` → continue. non‑zero → mapped by _failmode_. |
| confirm  | Immediately before `before` hooks.         | User Yes/No → `CONTINUE` or `ABORT`.             |
| after    | After a successful OS launch (or `SKIP`).  | Spawned via `subprocess.Popen`; never blocks.    |
| instead  | Replaces the OS launch.                    | `0` → `SKIP`. non‑zero → mapped by _failmode_.   |
| abort    | Forces the pipeline to abort regardless.   | `0` → `CONTINUE`. non‑zero → always `ABORT`.     |

**Examples**

```ini
[HOOKS]
.pdf = before|/usr/bin/evince {path} , instead|myviewer --file {path}
.exe = confirm|Run this file? , before|check_safety.sh {path}
.mttl = abort|test -f {path} && echo "OK"
```

## Sequential Hook Chaining

Hooks can be chained so that each hook depends on the previous one succeeding. When a hook fails, the pipeline's behavior depends on `launch_hook_failmode` and the hook's requirement level.

### Syntax

```ini
[HOOKS]
.exe = step1|validate.sh {path}, step2|backup.sh {path}, step3|launch.sh {path}
```

Each entry is executed in order. By default, every hook is considered "required". If a hook fails (non-zero exit code) and `launch_hook_failmode` is set to `abort`, the pipeline stops immediately and the launch is aborted.

### Execution Policy

1. **Required Hook** (default): If it fails, the pipeline obeys `launch_hook_failmode`. If failmode is `abort`, the entire launch is cancelled.
2. **Sequential Dependency**: If a hook fails and results in an `ABORT` outcome, subsequent hooks in the list are skipped.

## Confirmation Hooks

Confirmation hooks pause the pipeline and wait for user approval before continuing. They work in both GUI and headless modes.

### Syntax

```ini
[HOOKS]
.exe = confirm|⚠️ Execute {name} ? , before|run.sh {path}
```

### Behavior

- **GUI mode**: Displays a Yes/No dialog box.
- **Headless mode**: Prompts the user in the terminal (e.g., `Confirmation: ⚠️ Execute file.txt ? [y/N]: `).
- **Yes**: The pipeline continues to the next hook.
- **No / Cancel**: The pipeline resolves to `ABORT`, and the launch is cancelled.

Confirmation hooks are always synchronous and typically run before any other logic to ensure the user is aware of the impending action.

## Token Substitution

The template engine replaces the following placeholders before the command is split:

| Token        | Value                             |
| ------------ | --------------------------------- |
| `{path}`     | Absolute file path                |
| `{dir}`      | Parent directory of the file      |
| `{name}`     | Filename with extension           |
| `{cwd}`      | Current working directory         |
| `{ext}`      | Extension (including leading dot) |
| `{date}`     | ISO‑8601 date (e.g. `2026-07-31`) |
| `{hostname}` | Hostname of the local machine     |

Unknown tokens stay untouched.

**Illustration** (file `/prod/run1/ST_PRO_V2026.7.mttl` on host `build‑01`):

```ini
[HOOKS]
.mttl = before|echo "{name} from {dir} on {hostname} ({date})"
```

Expands to:

```
echo "ST_PRO_V2026.7.mttl from /prod/run1 on build-01 (2026-07-31)"
```

## Failmode Semantics

`launch_hook_failmode` governs non‑zero exits (including timeouts) for _blocking_ phases.

| Failmode | Phase   | Return code `0` | Return code != `0` | Resulting `HookOutcome`     | `ActionResult.message` sample              |
| -------- | ------- | --------------- | ------------------ | --------------------------- | ------------------------------------------ |
| warn     | before  | continue        | warn + continue    | `CONTINUE`                  | `"Hook warning, continue"`                 |
| warn     | instead | skip            | warn + continue    | `CONTINUE` (OS launch runs) |
| abort    | before  | continue        | abort + fail       | `ABORT`                     | `"aborted by a launch hook"`               |
| abort    | instead | skip            | abort + fail       | `ABORT`                     | `"aborted by a launch hook"`               |
| skip     | before  | continue        | skip + success     | `SKIP`                      | `"(OS launch replaced by 'instead' hook)"` |
| skip     | instead | skip            | skip + fail        | `SKIP`                      | `"(OS launch replaced by 'instead' hook)"` |

*The `abort` phase always yields `ABORT` regardless of *failmode\*.

## Timeout Behavior

`launch_hook_timeout` (default 30 s) applies to `before`, `instead` and `abort`
hooks. A `subprocess.TimeoutExpired` is converted to a `TimeoutError` and then
treated like a non‑zero exit – the configured _failmode_ decides the outcome.

```python
# Example: 5‑second timeout for a long‑running pre‑launch script
.mttl = before|sleep 60 && echo done
launch_hook_timeout = 5
launch_hook_failmode = abort
```

Result: the hook times out, logs a warning, and the launch aborts.

## Asynchronous `after` Hooks

`after` hooks fire via `subprocess.Popen`. Platform specifics:

- **Windows** – `creationflags=CREATE_NEW_PROCESS_GROUP|DETACHED_PROCESS`
- **POSIX** – `start_new_session=True`

Output streams are redirected to `DEVNULL`. Errors such as `FileNotFoundError`
are suppressed – a mis‑configured hook never crashes the caller.

## Quoting & CSV Splitting

The parser walks the raw value character by character, tracking a simple
`inside_quote` flag. Commas outside quotes split entries; commas inside double
quotes are kept.

**Path with comma**

```ini
.pdf = before|"C:\Program Files\My, Viewer\viewer.exe" "{path}"
```

**Multi‑argument command**

```ini
.sh = before|/bin/bash -c "echo start && sleep 1 && echo end"
```

Both parse correctly because the inner commas are quoted.

## Complete Examples

### 1. Log every `.mttl` launch with a timestamp

```ini
[HOOKS]
.mttl = before|logger "{date} launch {path}" , after|logger "{date} finished {path}"
launch_hook_failmode = warn
```

### 2. Replace the default PDF viewer

```ini
[HOOKS]
.pdf = instead|"/usr/local/bin/custom-pdfviewer" "{path}" , after|logger "PDF opened {path}"
launch_hook_failmode = abort
```

### 3. Abort `.exe` launch unless an approval flag exists

```ini
[HOOKS]
.exe = abort|test -f "{dir}/.launch_allowed" && echo OK
launch_hook_failmode = abort
```

When the flag file is missing the hook returns non‑zero, the pipeline aborts and the UI shows an error dialog.

### 4. Cleanup after temporary files

```ini
[HOOKS]
.tmp = after|/usr/bin/rm -f "{path}"
launch_hook_failmode = warn
```

The removal runs in the background after the OS opens the file (if any).

## Platform Notes

- **Windows** – `creationflags` combine `CREATE_NEW_PROCESS_GROUP` (`0x00000200`) and
  `DETACHED_PROCESS` (`0x00000008`).
- **POSIX** – `start_new_session=True` detaches the child from the parent’s process group.
- **Token splitting** – `shlex.split` uses POSIX rules on macOS/Linux and the native
  Windows lexer on Windows. Unbalanced quotes raise `ValueError` which is propagated
  as a hook failure.
- **GUI** – `launch_selected_file` shows a modal `messagebox.showerror` when the
  outcome is `ABORT`. In headless mode the error is returned via `ActionResult`.

## Troubleshooting

1. **Hook never runs** – extension key mismatch. Keys are normalized to lower‑case
   with a leading dot. `.PDF` and `pdf` both become `.pdf`.
2. **Comma splits incorrectly** – missing surrounding double quotes around the
   path that contains a comma.
3. **Timeout too short** – long‑running scripts exceed `launch_hook_timeout`. Increase the value or move the work to an `after` hook.
4. **GUI shows no error** – `abort` hooks always abort, but the GUI only displays
   an error if `launch_hook_failmode` is `abort`. Use `warn` to see warnings in the log.
5. **After hook never seen** – the pipeline short‑circuits with `ABORT` or `SKIP` before the `after` phase. Ensure the outcome is `CONTINUE`.
6. **Token not substituted** – misspelled token name; unknown tokens stay verbatim.
7. **Hook command not found** – `spawn_background_hook` swallows `FileNotFoundError` for `after` hooks; `before`/`instead` will raise a non‑zero exit.

## See Also

- [Configuration – ProFiles](./configuration-pylaunch.en.md)
- Source module: `src/profiles/core/environment/execution.py`

---

### Implementation Details (optional)

The parser in `parse_hook_entries` walks the raw string once, yielding a
`list[HookSpec]`. `HookSpec` stores `when` (phase) and the raw `template`. The
`when` value is lower‑cased and trimmed; unknown phases default to `before`.

The token substitution uses a plain dictionary lookup – no regex substitution –
so it is deterministic and fast (O(N) over the template length). The
substitution happens **before** `shlex.split`, allowing the user to embed spaces
in arguments via quoting.

`run_blocking_hook` executes the command with `subprocess.run(..., check=False)`
and captures `stdout`/`stderr`. The captured output is discarded; only the return
code matters. Errors from `shlex.split` (unbalanced quotes) raise `ValueError`
which surfaces as a non‑zero exit and is handled by the failmode logic.

`spawn_background_hook` deliberately swallows `FileNotFoundError` and generic
`OSError` to avoid crashing the launch pipeline. Errors are logged at _WARN_
level, matching the behaviour of the original implementation.

The `HookOutcome` enum maps directly to the `ActionResult` contract used by the
GUI and headless callers:

- `CONTINUE` – proceed to OS launch (or finish if no launch is needed).
- `SKIP` – treat as a successful launch; the GUI reports _SUCCESS_ with a note.
- `ABORT` – surface an error dialog in the GUI; headless callers receive a
  failed `ActionResult` with the message `"aborted by a launch hook"`.

The design intentionally keeps the hook pipeline side‑effect free except for the
commands themselves – no mutable global state is touched, enabling safe unit
testing. The test suite (`tests/test_launch_hooks.py`) exercises each phase,
failmode combination, and timeout scenario.

---

**Future enhancements** may include:

- Support for environment variable expansion (`${VAR}`) in templates.
- A built‑in `log` phase that writes to the application log without spawning a
  subprocess.
- Conditional hooks based on custom predicates (e.g., only on specific hostnames).

These can be added without breaking the existing contract; the parser will
ignore unknown keys and treat them as plain text.

---

_Document generated on 2026-08-02._

---

_End of reference._

Generated by the PyLaunch documentation system.

---

_This document is versioned with the codebase and updated alongside each release._

<!-- End of file -->
