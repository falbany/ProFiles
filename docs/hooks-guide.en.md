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
3. [Confirmation Guards (ask)](#confirmation-guards-ask)
4. [Token Substitution](#token-substitution)
5. [Rich Notifications (Markdown)](#rich-notifications-markdown)
6. [Error Handling and Failmode](#error-handling-and-failmode)
7. [Timeout Behavior](#timeout-behavior)
8. [Pattern Specificity (Pattern Matching)](#pattern-specificity-pattern-matching)
9. [Complete Examples](#complete-examples)
10. [Migration from Legacy INI Format](#migration-from-legacy-ini-format)
11. [Programming API](#programming-api)
12. [Troubleshooting](#troubleshooting)

---

## YAML Syntax and Structure

Workflows use a step-based YAML structure. Each entry in `hooks.entries` is a **glob pattern** that matches filenames.

### Basic Structure

```yaml
hooks:
  failmode: warn           # Global failure mode: "warn" | "abort" | "skip"
  timeout: 30              # Default timeout in seconds for blocking steps
  entries:
    "*.mttl":              # Glob pattern (all .mttl files)
      - action: notify
        content: "# Launching {{filename}}\\nPreparing environment..."
      - action: run
        content: "prepare_env.exe --file {{path}}"
        ask: "Run preparation script?"
        wait: true
        on_failure: stop
      - action: replace
        content: "special_launcher.exe {{path}}"
        ask: "Use special launcher?"
        wait: true
        on_failure: warn
    
    "special.mttl":        # More specific pattern (exact file)
      - action: notify
        content: "**Special processing** for this file."
      - action: run_after
        content: "logger.exe --special {{filename}}"
        wait: false
```

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
  content: "# Title\\n**Important message**\\n*Note: This is italic*"
  wait: true  # Blocks until user closes the dialog
```

**Behavior**:
- **GUI mode**: Displays Tkinter window with formatted text
- **Headless mode**: Prints formatted message to standard output
- **Always succeeds**: Cannot fail, so `on_failure` is ignored
- **Markdown support**: `# Heading`, `**bold**`, `*italic*`, `` `code` ``, `\\n`

### 2. `run` — Synchronous Execution

Executes a shell command and waits for completion.

```yaml
- action: run
  content: "prepare_env.exe --file {{path}} --verbose"
  wait: true           # Wait for completion (default)
  on_failure: stop     # stop | warn | continue
  timeout: 15          # Optional: override global timeout (seconds)
  if: "env:DEBUG"      # Optional: only run if DEBUG env var is set
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
  content: "logger.exe --opened {{filename}} --async"
  wait: false  # Always false for run_after
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
  content: "special_launcher.exe {{path}} --custom-args"
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
  content: "env_check.exe --verify {{dir}}"
  wait: true
  on_failure: warn
  timeout: 10          # Optional: override global timeout (seconds)
  if: "env:DEPLOY_ENV=prod"  # Optional: only run in production
```

**Behavior**:
- **Blocking**: Waits for command completion
- **Explicit verification**: Used to validate preconditions
- **Error handling**: Respects `on_failure`
- **Typical use**: Environment checks, prerequisites, validations

---

## Confirmation Guards (ask)

Each step can be protected by a **Yes/Skip/No** confirmation prompt.

```yaml
- action: run
  content: "dangerous_operation.exe {{path}}"
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
      content: "prepare.exe {{path}}"
      ask: "Prepare the file?"  # Yes/Skip/No
      
    - action: notify
      content: "Environment prepared."
      
    - action: run
      content: "validate.exe {{path}}"
      ask: "Validate before launch?"  # Yes/Skip/No
      
    - action: replace
      content: "special_launcher.exe {{path}}"
      ask: "Use special launcher?"  # Yes/Skip/No
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
| `{{content}}`  | Current step's content     | Useful in `ask` prompts   |
| `{{username}}` | Operator username          | `alice`                   |
| `{{hostname}}` | Machine hostname           | `workstation-01`          |
| `{{date}}`     | Today's date (ISO 8601)    | `2026-08-29`              |

### Usage Examples

```yaml
entries:
  "*.pdf":
    - action: notify
      content: "# Opening {{filename}}\\nPath: {{path}}"
      
    - action: run
      content: "tracker.exe --log {{filename}} --dir {{dir}}"
      
    - action: run_after
      content: "backup.exe {{path}} --timestamp {{date}}"
```

### `{{content}}` Token — Specific Use Case

The `{{content}}` token is substituted with the current step's `content` string. Useful for confirmation prompts:

```yaml
- action: run
  content: "special_tool.exe {{path}} --mode=advanced"
  ask: "Execute: {{content}}"
```

**Result**: The prompt will display "Execute: special_tool.exe test.mttl --mode=advanced"

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
  content: |
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
  failmode: warn    # Default behavior for failures
  timeout: 30       # Timeout in seconds for blocking steps
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
  content: "critical_setup.exe {{path}}"
  on_failure: abort  # Overrides global failmode
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
  timeout: 10  # Short timeout
  
entries:
  "*.mttl":
    - action: run
      content: "slow_command.exe {{path}}"
      # If > 10s: timeout → failure → failmode applied
```

---

## Timeout Behavior

### Global Timeout

Defined in `hooks.timeout` (default: 30 seconds).

```yaml
hooks:
  timeout: 60  # 60 seconds for all blocking steps
```

### Per-Step Timeout Override

Each step can override the global timeout with its own `timeout` field:

```yaml
hooks:
  timeout: 30  # Global default

entries:
  "*.mttl":
    - action: run
      content: "quick_check.exe {{path}}"
      timeout: 5    # Overrides global — 5 seconds for this step only
    - action: run
      content: "slow_build.exe {{path}}"
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
      content: "deploy.exe --production {{path}}"
      if: "env:DEPLOY_ENV"      # Executes only if DEPLOY_ENV is set
    - action: run
      content: "staging_deploy.exe {{path}}"
      if: "env:DEPLOY_ENV=prod"  # Executes only if DEPLOY_ENV equals "prod"
```

| Syntax            | Behavior                                  |
| ----------------- | ----------------------------------------- |
| `env:VAR_NAME`    | Step runs if `VAR_NAME` is **set** (any value) |
| `env:VAR=value`   | Step runs if `VAR_NAME` **equals** `value`  |

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
    "*.mttl":           # Low score — all .mttl
      - action: notify
        content: "Generic .mttl processing"
    
    "special.mttl":     # High score — exact file
      - action: notify
        content: "SPECIAL processing for special.mttl"
    
    "test?.mttl":       # Medium score — test1.mttl, test2.mttl
      - action: notify
        content: "Processing for test?.mttl"
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
        content: "# Launching {{filename}}\\nPreparing environment..."
      
      - action: run
        content: "prepare_env.exe --file {{path}} --verbose"
        ask: "Run preparation?"
        wait: true
        on_failure: stop
      
      - action: run
        content: "validate_env.exe --check {{dir}}"
        wait: true
        on_failure: warn
      
      - action: notify
        content: "**Environment ready**\\nLaunching..."
```

### Example 2: Custom Launcher with Confirmation

```yaml
hooks:
  failmode: abort
  timeout: 15
  entries:
    "*.exe":
      - action: notify
        content: "# Executing executable\\n**Warning** : Verify file origin."
        wait: true
      
      - action: run
        content: "antivirus.exe --scan {{path}}"
        ask: "Scan with antivirus?"
        wait: true
        on_failure: warn
      
      - action: replace
        content: "sandbox_launcher.exe {{path}}"
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
        content: "audit_logger.exe --opened {{filename}} --user {{username}} --time {{date}}"
        wait: false
      
      - action: run_after
        content: "backup.exe {{path}} --destination \\\\server\\backup"
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
        content: "check_dependencies.exe {{dir}}"
        ask: "Check dependencies?"
        wait: true
        on_failure: abort
      
      - action: notify
        content: "**Dependencies verified**\\nContinue launch?"
      
      - action: run
        content: "prepare_data.exe {{path}}"
        ask: "Prepare data?"
        wait: true
        on_failure: warn
      
      - action: run
        content: "special_tool.exe {{path}} --mode=advanced"
        ask: "Execute: {{content}}"
        wait: true
        on_failure: stop
```

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
        content="# Custom launch\\nFile: {{filename}}",
    ),
    WorkflowStep(
        action="run",
        content="prepare.exe {{path}}",
        wait=True,
        on_failure="stop",
    ),
    WorkflowStep(
        action="replace",
        content="custom_launcher.exe {{path}}",
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
def custom_ask_handler(message: str) -> Literal["yes", "skip", "no"]:
    """Custom confirmation prompt."""
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

**Cause**: Headless mode or missing Tkinter.

**Expected behavior**:
- In headless mode: Message printed to standard output
- If Tkinter missing: Automatic fallback to headless

**Solutions**:
1. Verify Tkinter installed (`python -m tkinter`)
2. In headless mode, check console for messages

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
