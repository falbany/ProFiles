# Launch Workflows — Reference

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.en.md)** |
> ⚙️ **[Configuration](./configuration-profile.en.md)** |
> 🔧 **Workflows** |
> 📊 **[Dynamic Columns](./dynamic-columns-guide.md)** |
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

---

Launch workflows let you run a sequence of actions around every file launch. The engine lives in
`src/profiles/core/environment/workflow.py` and is invoked by `launch_selected_file` in
`actions.py`. Workflows are configured in the `hooks` section of your `.profiles` configuration.

## YAML Syntax

Workflows use a step-based YAML structure. Each entry in `hooks.entries` is a glob pattern
supporting wildcards (`*`, `?`) and extension shorthands.

```yaml
hooks:
  failmode: warn           # warn | abort | skip
  timeout: 30              # seconds
  entries:
    "*.mttl":
      - action: notify
        content: "# Launching {filename}\\nPreparing environment..."
      - action: run
        content: "prepare_env.exe --file {path}"
        ask: "Run preparation script?"
      - action: replace
        content: "special_launcher.exe {path}"
        ask: "Use special launcher instead of OS default?"
    
    "special.mttl":
      - action: notify
        content: "**Special** processing for this file."
```

## Pattern Specificity

When multiple patterns match a filename, ProFiles selects the **most specific** one:
1. **Exact match** (e.g., `manual.pdf`) wins over wildcards.
2. **Question mark patterns** (e.g., `test?.txt`) win over star patterns.
3. **Star patterns** (e.g., `report_*.pdf`) win over extension shorthands.
4. **Extension shorthands** (e.g., `.pdf`) are the least specific.

## Workflow Actions

| Action      | Description                               | Blocking | Failure Handling             |
| ----------- | ----------------------------------------- | -------- | ---------------------------- |
| `notify`    | Show a Markdown message to the user.      | Optional | Never fails.                 |
| `run`       | Execute a shell command.                  | Yes      | Subject to `on_failure`.     |
| `run_after` | Spawn a background command.               | No       | Never blocks/stops workflow. |
| `replace`   | Execute command instead of OS launch.     | Yes      | Skips standard OS launch.    |
| `check`     | Execute command and check return code.    | Yes      | Subject to `on_failure`.     |

## Confirmation Guards (ask)

Any step can be guarded by an `ask` prompt. This displays a **Yes/Skip/No** dialog:
- **Yes**: Executes the current step and continues.
- **Skip**: Skips the current step and proceeds to the **next** step.
- **No**: Aborts the entire workflow (and the file launch).

## Rich Notifications (Markdown)

The `notify` action supports a subset of Markdown for clear communication:
- `# Heading`
- `**Bold text**`
- `*Italic text*`
- `` `Code snippets` ``
- `\\n` for new lines

## Token Substitution

The following placeholders are substituted at runtime:

| Token        | Value                             |
| ------------ | --------------------------------- |
| `{path}`     | Absolute file path                |
| `{dir}`      | Parent directory of the file      |
| `{filename}` | Filename with extension           |
| `{stem}`     | Filename without extension        |
| `{ext}`      | Extension (including leading dot) |

---

## Migration from INI/Legacy Hooks

The new workflow engine replaces the legacy INI `[HOOKS]` section. Existing hook strings
must be converted to the YAML step structure.

**Legacy INI:**
```ini
[HOOKS]
.mttl = before|echo "{path}" , instead|special_run {path}
```

**New YAML:**
```yaml
hooks:
  entries:
    ".mttl":
      - action: run
        content: "echo {path}"
      - action: replace
        content: "special_run {path}"
```
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
