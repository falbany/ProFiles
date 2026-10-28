# Launch Workflows — Complete Reference

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.en.md)** |
> ⚙️ **[Configuration](./configuration-profile.en.md)** |
> 🔧 **Workflows** |
> 📊 **[Dynamic Columns](./columns-guide.en.md)** |
> 🚀 **[Advanced Guide](./advanced/advanced-guide.en.md)**

---

Launch workflows constitute a powerful engine that executes a sequence of actions around every file launch. This system offers increased flexibility through structured YAML syntax and advanced features.

**Main engine**: `src/profiles/core/environment/workflow.py`  
**Orchestration**: `src/profiles/core/actions.py` (`launch_selected_file`)  
**Configuration**: `hooks` section in your `.profiles` file

## Table of Contents

1. [YAML Syntax and Structure](#yaml-syntax-and-structure)
2. [Available Actions](#available-actions)
3. [Message Display Rules](#message-display-rules)
4. [Confirmation Guards (ask)](#confirmation-guards-ask)
5. [Token Substitution](#token-substitution)
6. [Rich Notifications (Markdown)](#rich-notifications-markdown)
7. [Error Handling and Failmode](#error-handling-and-failmode)
8. [Command Output Capture](#command-output-capture)
9. [Timeout Behavior](#timeout-behavior)
10. [Pattern Specificity (Pattern Matching)](#pattern-specificity-pattern-matching)
11. [Complete Examples](#complete-examples)
12. [Migrating from `content:`](#migrating-from-content)
13. [Programming API](#programming-api)
14. [Troubleshooting](#troubleshooting)

---

## YAML Syntax and Structure

Workflows use a step-based YAML structure. Each entry in `hooks.entries` is a **glob pattern** that matches filenames.

Every step carries two purpose-specific keys: **`command:`** — the shell command template — and **`message:`** — a Markdown message shown to the user. Both keys are accepted on every action; which one is required depends on the action.

```yaml
hooks:
  failmode: warn # Global failure mode: "warn" | "abort" | "skip"
  timeout: 30 # Default timeout in seconds for blocking steps
  entries:
    "*.mttl": # Glob pattern (all .mttl files)
      - action: notify
        message: "# Launching {{filename}}\\nPreparing environment..."
      - action: run
        command: "prepare_env.exe --file {{path}}"
        message: "**Preparing** {{stem}}..."
        ask: "Run preparation script?"
        wait: true
        on_failure: stop
      - action: replace
        command: "special_launcher.exe {{path}}"
        ask: "Use special launcher?"
        wait: true
        on_failure: warn

    "special.mttl": # More specific pattern (exact file)
      - action: notify
        message: "**Special processing** for this file."
      - action: run_after
        command: "logger.exe --special {{filename}}"
        wait: false
```

> ⚠️ **Breaking change**: the old overloaded `content:` key is no longer
> recognized — a config still using it fails schema validation. See
> [Migrating from `content:`](#migrating-from-content).

### Glob Pattern Syntax

| Pattern        | Description             | Example                    |
| -------------- | ----------------------- | -------------------------- |
| `*`            | Zero or more characters | `*.pdf`, `report_*.txt`    |
| `?`            | Single character        | `test?.txt`, `data?.csv`   |
| `.ext`         | Shorthand for `*.ext`   | `.mttl`, `.pdf`            |
| `filename.ext` | Exact match             | `manual.pdf`, `readme.txt` |

**Priority rule**: When a file matches multiple patterns, the engine selects the **most specific** one:

1. Exact match (`manual.pdf`) > `?` > `*` > `.ext`
2. More specific patterns **override** generic patterns

---

## Available Actions

The engine supports **five action types**, each with specific behavior:

### 1. `notify` — User Notification

Displays a message to the user with partial Markdown support.

```yaml
- action: notify
  message: "# Title\\n**Important message**\\n*Note: This is italic*"
  wait: true # Blocks until user closes the dialog
```

**Behavior**:

- **Web mode (default)**: The notification appears as a workflow modal in the web frontend (the dialog opens in the desktop shell / browser; blocking steps wait for user confirmation in the UI)
- **Headless mode**: Prints formatted message to standard output
- **Legacy Tkinter backend**: Displays a Tkinter window with formatted text
- **Always succeeds**: Cannot fail, so `on_failure` is ignored
- **Markdown support**: `# Heading`, `**bold**`, `*italic*`, `` `code` ``, `\\n`

### 2. `run` — Synchronous Execution

Executes a shell command and waits for completion.

```yaml
- action: run
  command: "prepare_env.exe --file {{path}} --verbose"
  wait: true # Wait for completion (default)
  on_failure: stop # stop | warn | continue
  timeout: 15 # Optional: override global timeout (seconds)
  if: "env:DEBUG" # Optional: only run if DEBUG env var is set
```

**Behavior**:

- **Blocking**: Workflow waits for command completion
- **Output captured**: stdout/stderr captured (not displayed by default)
- **Return code**: 0 = success, non-0 = failure
- **Error handling**: Respects `on_failure` (see [Error Handling](#error-handling-and-failmode))

### 3. `run_after` — Asynchronous Execution

Launches a command in the background and continues immediately.

```yaml
- action: run_after
  command: "logger.exe --opened {{filename}} --async"
  wait: false # Always false for run_after
```

**Behavior**:

- **Non-blocking**: Workflow continues immediately
- **Detached process**: Child process is independent
- **Always succeeds**: Cannot fail (silent failures)
- **Typical use**: Logging, notifications, async cleanup

### 4. `replace` — Replace OS Launch

Executes a command **instead of** the default OS launch.

```yaml
- action: replace
  command: "special_launcher.exe {{path}} --custom-args"
  ask: "Use special launcher?"
  wait: true
```

**Behavior**:

- **Replaces OS launch**: Command runs INSTEAD of OS file association
- **Workflow ends**: After `replace`, workflow terminates (no OS launch)
- **Blocking**: Waits for command completion (if `wait: true`)
- **Typical use**: Custom launchers, emulators, special environments

### 5. `check` — Condition Verification

Executes a command and checks its return code.

```yaml
- action: check
  command: "env_check.exe --verify {{dir}}"
  wait: true
  on_failure: warn
  timeout: 10 # Optional: override global timeout (seconds)
  if: "env:DEPLOY_ENV=prod" # Optional: only run in production
```

**Behavior**:

- **Blocking**: Waits for command completion
- **Explicit verification**: Used to validate preconditions
- **Error handling**: Respects `on_failure`
- **Typical use**: Environment checks, prerequisites, validations

---

## Message Display Rules

Every step accepts an optional `message:` — this is what makes command steps
able to *talk to the user* (previously only `notify` steps could display text).

| Action       | `command:`                    | `message:`                                                    |
| ------------ | ----------------------------- | ------------------------------------------------------------- |
| `notify`     | Ignored (debug-logged)        | **Required.** Rendered with the Markdown subset below          |
| `run`        | **Required.** Executed        | Optional — see rules below                                     |
| `check`      | **Required.** Executed        | Optional — same as `run`                                       |
| `replace`    | **Required.** Executed        | Optional — same as `run`                                       |
| `run_after`  | **Required.** Spawned         | Optional — shown as a non-blocking notice when the step starts |

For `run` / `check` / `replace` / `run_after` steps carrying a `message:`:

- **With an `ask:` guard** — the Yes/Skip/No dialog displays the rendered
  Markdown `message` first, **then the `ask` question below it**. Without a
  `message:`, the dialog shows the question alone (unchanged).
- **Without an `ask:` guard** — the message is shown as a **non-blocking
  notice** (web UI notification; headless: printed to stdout) and the command
  executes. This is the feature the old `content:` design could not express:
  a `run` step that explains itself without a separate `notify` step.

```yaml
- action: run
  command: "prepare_env.exe --file {{path}}"
  message: "**Preparing** {{stem}} — this may take a few seconds."
  # No ask: the message appears as a non-blocking notice while the command runs.
```

---

## Confirmation Guards (ask)

Each step can be protected by a **Yes/Skip/No** confirmation prompt.

```yaml
- action: run
  command: "dangerous_operation.exe {{path}}"
  ask: "Are you sure you want to execute this dangerous operation?"
```

### Choice Behavior

| Choice   | Action                | Result                                      |
| -------- | --------------------- | ------------------------------------------- |
| **Yes**  | Executes current step | Continues to next step                      |
| **Skip** | Ignores current step  | Proceeds to **next** step                   |
| **No**   | Immediately aborts    | **Stops entire workflow** (and file launch) |

### Behavior on Last Step

If user chooses **Skip** on the **last** step:

- Workflow terminates
- OS launch is **skipped** (SKIP_LAUNCH)

### Example with Multiple Guards

```yaml
entries:
  "*.mttl":
    - action: run
      command: "prepare.exe {{path}}"
      ask: "Prepare the file?" # Yes/Skip/No

    - action: notify
      message: "Environment prepared."

    - action: run
      command: "validate.exe {{path}}"
      ask: "Validate before launch?" # Yes/Skip/No

    - action: replace
      command: "special_launcher.exe {{path}}"
      ask: "Use special launcher?" # Yes/Skip/No
```

**Scenarios**:

- **Yes → Yes → Yes**: All steps executed, special launcher used
- **Yes → Skip → Yes**: Step 2 skipped, special launcher used
- **Skip** (first): Step 1 skipped, continues to next steps
- **No** (anywhere): Workflow aborted, file **not launched**

---

## Token Substitution

The engine automatically substitutes **placeholders** at runtime.

### Available Tokens

| Token          | Value                      | Example                   |
| -------------- | -------------------------- | ------------------------- |
| `{{path}}`     | Absolute file path         | `C:\\Projects\\test.mttl` |
| `{{dir}}`      | Parent directory           | `C:\\Projects\\`          |
| `{{filename}}` | Filename with extension    | `test.mttl`               |
| `{{stem}}`     | Filename without extension | `test`                    |
| `{{ext}}`      | Extension (with dot)       | `.mttl`                   |
| `{{command}}`  | Step's resolved `command`  | Useful in `ask` prompts   |
| `{{message}}`  | Step's resolved `message`  | Useful in `ask` prompts   |
| `{{output}}`   | Captured output of the most recent completed blocking command step (empty string before any) | Probe result text |
| `{{username}}` | Operator username          | `alice`                   |
| `{{hostname}}` | Machine hostname           | `workstation-01`          |
| `{{date}}`     | Today's date (ISO 8601)    | `2026-08-29`              |

### Usage Examples

```yaml
entries:
  "*.pdf":
    - action: notify
      message: "# Opening {{filename}}\\nPath: {{path}}"

    - action: run
      command: "tracker.exe --log {{filename}} --dir {{dir}}"

    - action: run_after
      command: "backup.exe {{path}} --timestamp {{date}}"
```

### `{{command}}` / `{{message}}` Tokens — Current Step Values

The `{{command}}` and `{{message}}` tokens resolve to the current step's command and message. Useful in confirmation prompts:

```yaml
- action: run
  command: "special_tool.exe {{path}} --mode=advanced"
  message: |
    # Advanced mode
    This tool applies **special processing** to {{stem}}.
  ask: "Execute: {{command}}"
```

**Result**: The dialog shows the Markdown message first, then "Execute: special_tool.exe test.mttl --mode=advanced". Both the `{{token}}` and single-brace `{token}` forms are accepted.

---

## Rich Notifications (Markdown)

The `notify` action supports a **subset of Markdown** for clear communication.

### Supported Syntax

| Syntax        | Rendered        | Example                      |
| ------------- | --------------- | ---------------------------- |
| `# Title`     | Heading level 1 | `# Launching...`             |
| `## Subtitle` | Heading level 2 | `## Preparation...`          |
| `**bold**`    | Bold text       | `**Important** : Check data` |
| `*italic*`    | Italic text     | `*Note* : This is optional`  |
| `` `code` ``  | Monospace text  | `` `command.exe --arg` ``    |
| `\\n`         | New line        | `Line 1\\nLine 2`            |

### Complete Notification Example

```yaml
- action: notify
  message: |
    # Launching {{filename}}

    **Status** : Preparing environment...

    *Note* : This operation may take a few seconds.

    Command: `prepare_env.exe --file {{path}}`
```

**GUI Rendering**:

- Large bold title
- Bold text for "Important"
- Italic text for notes
- Monospace code
- Spaced layout

**Headless Rendering**:

- Plain text with escape sequences
- Markdown stripped (see `render_text()` in `src/profiles/core/environment/render.py`)

---

## Error Handling and Failmode

### Global Parameters

```yaml
hooks:
  failmode: warn # Default behavior for failures
  timeout: 30 # Timeout in seconds for blocking steps
```

### Failure Modes (`failmode`)

| Mode    | Behavior                                    | Use Case                        |
| ------- | ------------------------------------------- | ------------------------------- |
| `warn`  | Warns user, continues to next step          | **Default** — fault-tolerant    |
| `abort` | Immediately cancels workflow                | Strict — failure = total stop   |
| `skip`  | Skips rest of workflow, returns SKIP_LAUNCH | Graceful stop without OS launch |

### Per-Step `on_failure` Parameter

Each step can override the global `failmode`:

```yaml
- action: run
  command: "critical_setup.exe {{path}}"
  on_failure: abort # Overrides global failmode
```

**Possible values**:

- `stop`: Stops workflow (equivalent to `abort`)
- `warn`: Warns but continues (equivalent to `warn`)
- `continue`: Suppresses error and continues (similar to `warn` but no warning)

### Priority Hierarchy

1. **Per-step `on_failure`** > global `failmode`
2. **`abort`** (pattern) > global `failmode`
3. **`requires_success: false`** (legacy) > `requires_success: true`

### Timeout Behavior

A timeout counts as a **failure** (non-0 return code):

```yaml
hooks:
  timeout: 10 # Short timeout

entries:
  "*.mttl":
    - action: run
      command: "slow_command.exe {{path}}"
      # If > 10s: timeout → failure → failmode applied
```

---

## Command Output Capture

Blocking command steps (`run` with `wait: true`, `check`, `replace`) capture
the **combined stdout + stderr** of the command (tail-bounded to ~4 KB;
anything longer is cut with a leading `…` marker). The `output:` key
controls what happens with it:

| Value       | During execution                                | On failure                          |
| ----------- | ----------------------------------------------- | ----------------------------------- |
| `hide` (default) | Captured and discarded (not displayed)     | Exit code included in the failure notice, no output |
| `show`      | Shown to the user as a non-blocking notice after the command completes | Same notice includes the output |
| `fail_only` | Captured, discarded on success                  | Failure notice includes the output  |

```yaml
"*.mttl":
  - action: check
    command: "probe_env.exe --verify {{dir}}"
    output: fail_only
    on_failure: warn
  - action: run
    command: "prepare.exe --from {{dir}}"
    message: "**Probe result:**\\n`{{output}}`" # captured output of the check
```

### The `{{output}}` token

Any step after a blocking command step can reference the captured output
of the **most recent completed command step** via the `{{output}}` token
(single-brace `{output}` also works). Before any command step has run,
it resolves to an empty string. It works in `message:`, `command:`,
`ask:` — anywhere tokens are accepted — and is substituted before the
text is shown. Wrap it in backticks in your Markdown for monospace
rendering. Multi-line output renders naturally; truncated output starts
with the `…` marker.

### Failure notices

Failing command steps always record their **exit code**, regardless of
`output:`. Failure descriptions read:

```
Step failed (rc=2): env_check.exe --verify C:\Projects
Last output:
  ERROR: missing PROD license
```

The `Last output:` block is appended only when the failing step sets
`output: show` or `fail_only`.

### Behavior notes

- `output:` applies **only to blocking command steps**. On `run_after`
  (or `run` with `wait: false`) it is ignored and a debug message is
  logged to the profiles log (the spawn is detached — nothing to capture).
- Because blocking commands are now captured, their output **no longer
  leaks into the ProFiles console**: child processes write to the capture
  buffer instead of the console (headless mode still prints notices).
- Output is decoded with the locale's preferred encoding; undecodable
  bytes become the Unicode replacement character (�).

---

## Timeout Behavior

### Global Timeout

Defined in `hooks.timeout` (default: 30 seconds).

```yaml
hooks:
  timeout: 60 # 60 seconds for all blocking steps
```

### Per-Step Timeout Override

Each step can override the global timeout with its own `timeout` field:

```yaml
hooks:
  timeout: 30 # Global default

entries:
  "*.mttl":
    - action: run
      command: "quick_check.exe {{path}}"
      timeout: 5 # Overrides global — 5 seconds for this step only
    - action: run
      command: "slow_build.exe {{path}}"
      # Uses global 30s timeout
```

When a per-step `timeout` is set, it takes precedence over `hooks.timeout`.
A timeout results in a failure outcome (non-0 return code) and triggers the step's `on_failure` resolution.

**Applies to**: `run`, `check`, and `replace` actions.

### Asynchronous Commands (`run_after`)

`run_after` steps are **not subject to timeout**:

- They are launched in background
- Workflow continues immediately
- Spawn failures are silent

---

## Conditional Execution (`if`)

Each step can include an `if` condition that controls whether the step executes.

### Environment Variable Checks

The `if` field supports environment variable checks:

```yaml
entries:
  "*.mttl":
    - action: run
      command: "deploy.exe --production {{path}}"
      if: "env:DEPLOY_ENV" # Executes only if DEPLOY_ENV is set
    - action: run
      command: "staging_deploy.exe {{path}}"
      if: "env:DEPLOY_ENV=prod" # Executes only if DEPLOY_ENV equals "prod"
```

| Syntax          | Behavior                                       |
| --------------- | ---------------------------------------------- |
| `env:VAR_NAME`  | Step runs if `VAR_NAME` is **set** (any value) |
| `env:VAR=value` | Step runs if `VAR_NAME` **equals** `value`     |

If the condition is **not met**, the step is silently skipped — the workflow continues to the next step.

---

The engine uses a **scoring algorithm** to determine the most specific pattern.

### Specificity Algorithm

1. **Exact match** (`manual.pdf`) → Highest score
2. **`?` pattern** (`test?.txt`) → High score
3. **`*` pattern** (`report_*.pdf`) → Medium score
4. **Extension shorthand** (`.pdf`) → Lowest score

### Priority Example

```yaml
hooks:
  entries:
    "*.mttl": # Low score — all .mttl
      - action: notify
        message: "Generic .mttl processing"

    "special.mttl": # High score — exact file
      - action: notify
        message: "SPECIAL processing for special.mttl"

    "test?.mttl": # Medium score — test1.mttl, test2.mttl
      - action: notify
        message: "Processing for test?.mttl"
```

**Results**:

- `special.mttl` → Uses pattern `special.mttl` (exact)
- `test1.mttl` → Uses pattern `test?.mttl` (`?` > `*`)
- `other.mttl` → Uses pattern `*.mttl` (generic)

### Implementation

See `src/profiles/core/environment/matcher.py` for scoring algorithm.

---

## Complete Examples

### Example 1: Standard Preparation Workflow

```yaml
hooks:
  failmode: warn
  timeout: 30
  entries:
    "*.mttl":
      - action: notify
        message: "# Launching {{filename}}\\nPreparing environment..."

      - action: run
        command: "prepare_env.exe --file {{path}} --verbose"
        message: "**Preparing** {{stem}}..."
        ask: "Run preparation?"
        wait: true
        on_failure: stop

      - action: run
        command: "validate_env.exe --check {{dir}}"
        wait: true
        on_failure: warn

      - action: run
        command: "notify_user.exe --done {{filename}}"
        message: "**Environment ready**\\nLaunching..."
```

### Example 2: Custom Launcher with Confirmation

```yaml
hooks:
  failmode: abort
  timeout: 15
  entries:
    "*.exe":
      - action: notify
        message: "# Executing executable\\n**Warning** : Verify file origin."
        wait: true

      - action: run
        command: "antivirus.exe --scan {{path}}"
        ask: "Scan with antivirus?"
        wait: true
        on_failure: warn

      - action: replace
        command: "sandbox_launcher.exe {{path}}"
        ask: "Execute in sandbox?"
        wait: true
        on_failure: stop
```

### Example 3: Logging and Audit

```yaml
hooks:
  failmode: warn
  timeout: 10
  entries:
    "*.pdf":
      - action: run_after
        command: "audit_logger.exe --opened {{filename}} --user {{username}} --time {{date}}"
        wait: false

      - action: run_after
        command: "backup.exe {{path}} --destination \\\\server\\backup"
        wait: false
```

### Example 4: Conditional Workflow with Multiple Guards

```yaml
hooks:
  failmode: warn
  timeout: 30
  entries:
    "*.mttl":
      - action: run
        command: "check_dependencies.exe {{dir}}"
        ask: "Check dependencies?"
        wait: true
        on_failure: abort

      - action: run
        command: "verify_deps_viewer.exe {{dir}}"
        message: "**Dependencies verified**"
        if: "env:SHOW_DEP_STATUS"

      - action: run
        command: "prepare_data.exe {{path}}"
        ask: "Prepare data?"
        wait: true
        on_failure: warn

      - action: run
        command: "special_tool.exe {{path}} --mode=advanced"
        message: |
          # Advanced mode
          This tool applies **special processing** to {{stem}}.
        ask: "Execute: {{command}}"
        wait: true
        on_failure: stop
```

## Migrating from `content:`

> ⚠️ **Breaking change** (no legacy alias, by design). Config files still
> using `content:` inside a workflow step fail YAML schema validation with
> the generic unknown-key error.

| Old key                                           | New key                        |
| ------------------------------------------------- | ------------------------------ |
| `content:` on `notify`                            | `message:`                     |
| `content:` on `run`/`check`/`replace`/`run_after` | `command:`                     |
| `{{content}}` in `ask:`                           | `{{command}}` or `{{message}}` |

### Before

```yaml
"*.mttl":
  - action: notify
    content: "# Launching {{filename}}\\nPreparing environment..."
  - action: run
    content: "prepare_env.exe --file {{path}}"
    ask: "Run preparation script for {{stem}}?"
```

### After

```yaml
"*.mttl":
  - action: notify
    message: "# Launching {{filename}}\\nPreparing environment..."
  - action: run
    command: "prepare_env.exe --file {{path}}"
    message: "**Preparing** {{stem}}..."
    ask: "Run preparation script for {{stem}}?"
```

Note the second benefit: a `run` step can now carry its own `message:` — the
separate `notify` step previously required to show text alongside a command
is often no longer needed (see [Message Display Rules](#message-display-rules)).

### Validation errors you may see

- `content:` inside a step → `Extra inputs are not permitted` (unknown key).
- `notify` without `message:` → `a 'notify' step requires 'message'`
  (the error names the hooks entry pattern, e.g. `hooks entry '*.mttl'`).
- `run` / `check` / `replace` / `run_after` without `command:` →
  `a 'run' step requires 'command'` (same pattern-aware error).
- `command:` on a `notify` step → **valid**, the key is ignored and a
  debug-level line is logged.

---

## Programming API

For advanced users wanting to integrate the engine into their own code.

### Main Module

```python
from profiles.core.environment.workflow import (
    run_workflow,
    WorkflowOutcome,
)
from profiles.core.config.models import WorkflowStep
```

### Programmatic Usage Example

```python
from pathlib import Path
from profiles.core.environment.workflow import run_workflow, WorkflowOutcome
from profiles.core.config.models import WorkflowStep

# Define steps
steps = [
    WorkflowStep(
        action="notify",
        message="# Custom launch\\nFile: {{filename}}",
    ),
    WorkflowStep(
        action="run",
        command="prepare.exe {{path}}",
        message="**Preparing** the file...",
        wait=True,
        on_failure="stop",
    ),
    WorkflowStep(
        action="replace",
        command="custom_launcher.exe {{path}}",
        wait=True,
    ),
]

# Execute workflow
file_path = Path("C:\\test.mttl")
outcome = run_workflow(
    steps=steps,
    file_path=file_path,
    headless=False,
    # ask_callback=custom_ask_handler,  # Optional
    # notify_callback=custom_notify_handler,  # Optional
)

# Handle result
if outcome == WorkflowOutcome.CONTINUE:
    # Launch with default OS association
    launch_file(file_path)
elif outcome == WorkflowOutcome.SKIP_LAUNCH:
    # Workflow completed, no OS launch
    print("Workflow completed, no OS launch")
elif outcome == WorkflowOutcome.ABORT:
    # Workflow aborted (by user or error)
    print("Workflow aborted")
```

### Custom Callbacks

```python
def custom_ask_handler(message: str, pre_message: str | None) -> Literal["yes", "skip", "no"]:
    """Custom confirmation prompt.

    ``pre_message`` carries the step's rendered Markdown ``message`` (None
    when the step has none); display it above the question when present.
    """
    if pre_message:
        print(pre_message)
    print(f"Question: {message}")
    response = input("[y/s/N]: ").strip().lower()
    if response in ("y", "yes"):
        return "yes"
    if response in ("s", "skip"):
        return "skip"
    return "no"


def custom_notify_handler(message: str, blocking: bool) -> None:
    """Custom notification."""
    print(f"[NOTICE] {message}")


# Use callbacks
outcome = run_workflow(
    steps=steps,
    file_path=file_path,
    ask_callback=custom_ask_handler,
    notify_callback=custom_notify_handler,
)
```

---

## Troubleshooting

### Problem: Hook Never Runs

**Cause**: Pattern specificity or matching mismatch.

**Solutions**:

1. Verify pattern matches file (e.g., `.mttl` vs `*.mttl`)
2. Use more specific pattern (e.g., `special.mttl` instead of `*.mttl`)
3. Check file extension (case-sensitive?)

**Debug**: Enable logging `verbose: DEBUG` in `.profiles`

### Problem: Variables Remain Literal

**Cause**: Incorrect token spelling.

**Solutions**:

1. Verify syntax: `{{path}}`, `{{filename}}`, `{{dir}}`, `{{ext}}`, `{{stem}}`
2. Ensure **double braces** on each side
3. Verify file exists (tokens require valid `file_path`)

### Problem: Notification Dialog Doesn't Appear

**Cause**: Headless mode, or the notification is waiting in the web UI.

**Expected behavior**:

- In web mode: The notification opens as a workflow modal in the frontend (check the desktop window / browser tab)
- In headless mode: Message printed to standard output
- Legacy Tkinter backend missing Tkinter: automatic fallback to headless

**Solutions**:

1. In web mode, look at the workflow modal in the frontend (it may be awaiting your confirmation)
2. In headless mode, check console for messages
3. With `--tkinter`, verify Tkinter is installed (`python -m tkinter`)

### Problem: Frequent Timeout

**Cause**: Commands too slow for configured timeout.

**Solutions**:

1. Increase `hooks.timeout` in `.profiles`
2. Set a per-step `timeout` to override the global value for slow commands
3. Use `action: run_after` for long-running background commands
4. Optimize command to be faster

### Problem: Workflow Doesn't Stop on Failure

**Cause**: `failmode` or `on_failure` misconfigured.

**Solutions**:

1. Verify `failmode: abort` for strict behavior
2. Add `on_failure: stop` to critical steps
3. Use `action: check` for explicit validations

### Problem: `if` Condition Step Not Running

**Cause**: Environment variable check not met.

**Solutions**:

1. Verify the variable is set in the environment before launching
2. Use `env:VAR` for existence checks or `env:VAR=value` for equality
3. Remember: skipped steps are **silent** — no warning is logged

---

## Technical References

### Source Files

- **Workflow engine**: `src/profiles/core/environment/workflow.py`
- **Legacy hooks management**: `src/profiles/core/environment/execution.py`
- **Data models**: `src/profiles/core/config/models.py`
- **Confirmation dialog**: `src/profiles/core/environment/interactions.py`
- **Notification dialog**: `src/profiles/core/environment/message_dialog.py`
- **Markdown rendering**: `src/profiles/core/environment/render.py`
- **Pattern matching**: `src/profiles/core/environment/matcher.py`

### Key Classes and Functions

- `WorkflowStep`: Data model for a step
- `run_workflow()`: Main execution function
- `WorkflowOutcome`: Result enumeration (CONTINUE, SKIP_LAUNCH, ABORT)
- `confirm_dialog_3way()`: Yes/Skip/No dialog
- `show_notify_dialog()`: Notification dialog
- `render_text()`: Markdown rendering to GUI/Headless

---

_Document generated on 2026-08-07._

---

_End of reference._
