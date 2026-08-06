# Launch Workflows — Reference

> 🏠 **[Documentation Home](./README.md)** |
> 📦 **[Installation](./installation-guide.en.md)** |
> ⚙️ **[Configuration](./configuration-profile.en.md)** |
> 🔧 **Workflows** |
> 📊 **[Dynamic Columns](./columns-guide.en.md)** |
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
        content: "# Launching {{filename}}\\nPreparing environment..."
      - action: run
        content: "prepare_env.exe --file {{path}}"
        ask: "Run preparation script?"
      - action: replace
        content: "special_launcher.exe {{path}}"
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
| `{{path}}`     | Absolute file path                |
| `{{dir}}`      | Parent directory of the file      |
| `{{filename}}` | Filename with extension           |
| `{{stem}}`     | Filename without extension        |
| `{{ext}}`      | Extension (including leading dot) |
| `{{content}}`  | The `content` string of the current step (useful in `ask` prompts) |

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
        content: "echo {{path}}"
      - action: replace
        content: "special_run {{path}}"
```

## Failmode Semantics

`launch_hook_failmode` governs non‑zero exits for workflow steps.

- **warn**: Warn the user during execution, but proceed to the next step.
- **abort**: Cancel the workflow execution and halt subsequent file operations.
- **continue**: Suppress errors and advance with workflow steps.

## Timeout Behavior

`launch_hook_timeout` (default 30 s) applies to blocking steps. A command timeout counts as a non-zero exit and triggers the configured failure mode (`on_failure` / `failmode`).

## Troubleshooting

1. **Hook never runs** – glob specificity or mismatch. The engine automatically scores patterns like `special.mttl` higher than `*.mttl`.
2. **Variable placeholder stays literal** – verify spelling. The variables are runtime expanded (e.g. `{{filename}}`, `{{path}}`).
3. **Notify dialog does not pop up** – in headless mode or if Tkinter is missing, the engine automatically prints the notification text to standard output instead.

---

_Document generated on 2026-08-06._

---

_End of reference._
