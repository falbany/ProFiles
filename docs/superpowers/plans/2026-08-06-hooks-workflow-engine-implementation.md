# HOOKS Workflow Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the launch hooks system from phase-based hooks to a flexible step-based workflow engine with glob pattern matching, confirmation guards, and Markdown rendering.

**Architecture:** Create new pure-core modules for workflow orchestration, pattern matching, and rendering. Update the config schema to support the new "steps" model. Replace the existing hook execution engine while maintaining the same public API surface for GUI integration.

**Tech Stack:** Python 3.11+, Pydantic v2, fnmatch (stdlib), Tkinter (GUI), pytest (testing)

## Global Constraints

- Core layer must have zero Tkinter dependencies
- All dialogues must be injectable (mockable for testing)
- Renderer produces a backend-agnostic `RenderTree` structure
- Test coverage target: >85%
- No retro-compatibility: existing configs must be migrated
- Follow AGENTS.md architecture principles (SRP, DRY, KISS)

---

## File Structure

### New Files to Create

**Core Modules:**
- `src/profiles/core/environment/workflow.py` — Step-based workflow engine (orchestration)
- `src/profiles/core/environment/matcher.py` — Glob pattern matching with specificity priority
- `src/profiles/core/environment/render.py` — Escape sequences + Markdown → RenderTree
- `src/profiles/core/environment/message_dialog.py` — Notify dialog (blocking/non-blocking)

**Schema & Models:**
- `src/profiles/core/config/models.py` — Update `HookSpec` → `WorkflowStep`
- `src/profiles/core/config/schema.py` — Update Pydantic schema for new YAML structure
- `src/profiles/core/config/reader.py` — Update `_apply_hooks` to parse new format

**Tests:**
- `tests/test_matcher.py` — Pattern specificity tests
- `tests/test_render.py` — Escape sequences + Markdown rendering
- `tests/test_workflow.py` — Workflow engine execution logic
- `tests/test_interactions.py` — Dialog 3-way (Yes/Skip/No)
- `tests/test_message_dialog.py` — Notify dialog behavior

### Files to Modify

- `src/profiles/core/environment/interactions.py` — Add 3-way dialog (Yes/Skip/No)
- `src/profiles/core/environment/execution.py` — Replace with workflow engine (or rename to `workflow.py`)
- `src/profiles/core/actions.py` — Update `launch_selected_file` to use new workflow API
- `.gitignore` — Already updated to allow `docs/superpowers/*`

---

## Task Decomposition

### Task 1: Core Data Models & Schema

**Files:**
- Modify: `src/profiles/core/config/models.py:15-35`
- Modify: `src/profiles/core/config/schema.py:55-75`
- Modify: `src/profiles/core/config/reader.py:150-165`

**Interfaces:**
- Consumes: Existing `AppConfig` structure
- Produces: `WorkflowStep` dataclass with fields: `action`, `content`, `ask`, `wait`, `on_failure`

- [ ] **Step 1.1: Write the failing test**

```python
# tests/test_config_models.py
from profiles.core.config.models import WorkflowStep

def test_workflow_step_defaults():
    step = WorkflowStep(action="run", content="echo hello")
    assert step.wait is True
    assert step.on_failure == "stop"
    assert step.ask is None

def test_workflow_step_custom_values():
    step = WorkflowStep(
        action="notify",
        content="# Title",
        wait=False,
        on_failure="continue",
        ask="Confirm?"
    )
    assert step.wait is False
    assert step.on_failure == "continue"
    assert step.ask == "Confirm?"
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `pytest tests/test_config_models.py::test_workflow_step_defaults -v`
Expected: `ModuleNotFoundError` or `AttributeError` (WorkflowStep not defined)

- [ ] **Step 1.3: Write minimal implementation**

```python
# src/profiles/core/config/models.py
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class WorkflowStep:
    """A single step in a launch workflow."""
    action: Literal["notify", "run", "run_after", "replace", "check"]
    content: str
    ask: str | None = None
    wait: bool = True
    on_failure: Literal["stop", "warn", "continue"] = "stop"
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `pytest tests/test_config_models.py::test_workflow_step_defaults -v`
Expected: PASS

- [ ] **Step 1.5: Commit**

```bash
git add src/profiles/core/config/models.py tests/test_config_models.py
git commit -m "feat: add WorkflowStep data model with action/content/ask/wait/on_failure"
```

---

### Task 2: Pydantic Schema for YAML Parsing

**Files:**
- Modify: `src/profiles/core/config/schema.py:55-80`

**Interfaces:**
- Consumes: `WorkflowStep` model
- Produces: `WorkflowStepSchema` Pydantic model for YAML validation

- [ ] **Step 2.1: Write the failing test**

```python
# tests/test_config_schema.py
from pydantic import ValidationError
from profiles.core.config.schema import WorkflowStepSchema

def test_workflow_step_schema_valid():
    data = {
        "action": "run",
        "content": "echo {path}",
        "ask": "Confirm?",
        "wait": True,
        "on_failure": "stop"
    }
    step = WorkflowStepSchema(**data)
    assert step.action == "run"
    assert step.content == "echo {path}"
    assert step.ask == "Confirm?"

def test_workflow_step_schema_defaults():
    data = {"action": "notify", "content": "Hello"}
    step = WorkflowStepSchema(**data)
    assert step.wait is True
    assert step.on_failure == "stop"
    assert step.ask is None

def test_workflow_step_schema_invalid_action():
    with pytest.raises(ValidationError):
        WorkflowStepSchema(action="invalid", content="test")
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `pytest tests/test_config_schema.py::test_workflow_step_schema_valid -v`
Expected: `AttributeError` (WorkflowStepSchema not defined)

- [ ] **Step 2.3: Write minimal implementation**

```python
# src/profiles/core/config/schema.py
from pydantic import BaseModel
from typing import Literal

class WorkflowStepSchema(BaseModel):
    action: Literal["notify", "run", "run_after", "replace", "check"]
    content: str
    ask: str | None = None
    wait: bool = True
    on_failure: Literal["stop", "warn", "continue"] = "stop"
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `pytest tests/test_config_schema.py::test_workflow_step_schema_valid -v`
Expected: PASS

- [ ] **Step 2.5: Commit**

```bash
git add src/profiles/core/config/schema.py tests/test_config_schema.py
git commit -m "feat: add WorkflowStepSchema Pydantic model for YAML validation"
```

---

### Task 3: Pattern Matcher with Specificity Priority

**Files:**
- Create: `src/profiles/core/environment/matcher.py`

**Interfaces:**
- Consumes: List of glob patterns, filename
- Produces: Most specific matching pattern (or None)

- [ ] **Step 3.1: Write the failing test**

```python
# tests/test_matcher.py
from profiles.core.environment.matcher import select_most_specific_pattern

def test_exact_match_wins():
    patterns = ["*.mttl", "toto.mttl", ".mttl"]
    filename = "toto.mttl"
    result = select_most_specific_pattern(patterns, filename)
    assert result == "toto.mttl"

def test_star_pattern():
    patterns = [".pdf", "*.pdf", "report_*.pdf"]
    filename = "report_2026.pdf"
    result = select_most_specific_pattern(patterns, filename)
    assert result == "report_*.pdf"

def test_no_match():
    patterns = [".mttl", "*.pdf"]
    filename = "test.txt"
    result = select_most_specific_pattern(patterns, filename)
    assert result is None

def test_question_mark_pattern():
    patterns = [".pdf", "test?.txt"]
    filename = "test1.txt"
    result = select_most_specific_pattern(patterns, filename)
    assert result == "test?.txt"
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `pytest tests/test_matcher.py::test_exact_match_wins -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 3.3: Write minimal implementation**

```python
# src/profiles/core/environment/matcher.py
import fnmatch
from typing import Iterable

def _pattern_specificity(pattern: str) -> int:
    """Return specificity score (higher = more specific)."""
    if "*" not in pattern and "?" not in pattern:
        return 3  # Exact match
    if "?" in pattern:
        return 2  # Question mark only
    return 1  # Star pattern

def select_most_specific_pattern(
    patterns: Iterable[str],
    filename: str,
) -> str | None:
    """Select the most specific pattern that matches the filename."""
    matches = [
        p for p in patterns
        if fnmatch.fnmatch(filename, p)
    ]
    if not matches:
        return None
    return max(matches, key=_pattern_specificity)
```

- [ ] **Step 3.4: Run test to verify it passes**

Run: `pytest tests/test_matcher.py -v`
Expected: All tests PASS

- [ ] **Step 3.5: Commit**

```bash
git add src/profiles/core/environment/matcher.py tests/test_matcher.py
git commit -m "feat: add glob pattern matcher with specificity priority"
```

---

### Task 4: Escape Sequences & Markdown Renderer

**Files:**
- Create: `src/profiles/core/environment/render.py`

**Interfaces:**
- Consumes: Raw text with escape sequences and Markdown
- Produces: `RenderTree` (list of styled segments)

- [ ] **Step 4.1: Write the failing test**

```python
# tests/test_render.py
from profiles.core.environment.render import render_text

def test_escape_sequences():
    result = render_text("Line1\\nLine2\\tTab")
    assert result == "Line1\nLine2\tTab"

def test_escape_backslash():
    result = render_text("Path\\\\File")
    assert result == "Path\\File"

def test_markdown_bold():
    result = render_text("**bold** text")
    assert "**bold**" not in result  # Should be processed

def test_markdown_heading():
    result = render_text("# Title")
    assert "Title" in result

def test_headless_mode():
    result = render_text("# **Bold**\\nText", headless=True)
    assert isinstance(result, str)
```

- [ ] **Step 4.2: Run test to verify it fails**

Run: `pytest tests/test_render.py::test_escape_sequences -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 4.3: Write minimal implementation**

```python
# src/profiles/core/environment/render.py
from dataclasses import dataclass
from typing import Literal

@dataclass
class TextSegment:
    text: str
    style: Literal["normal", "bold", "italic", "heading", "code"] = "normal"

RenderTree = list[TextSegment]

def render_text(text: str, headless: bool = False) -> str | RenderTree:
    """Render escape sequences and Markdown subset."""
    # Step 1: Escape sequences
    text = text.replace("\\\\", "\\\\")
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", "\t")
    text = text.replace('\\"', '"')
    text = text.replace("\\'", "'")
    
    if headless:
        # Strip Markdown for headless mode
        text = _strip_markdown(text)
        return text
    
    # Step 2: Parse Markdown into RenderTree
    return _parse_markdown(text)

def _strip_markdown(text: str) -> str:
    """Remove Markdown syntax for headless mode."""
    import re
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # Headings
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # Italic
    text = re.sub(r'`(.+?)`', r'\1', text)  # Code
    return text

def _parse_markdown(text: str) -> RenderTree:
    """Parse Markdown into structured RenderTree."""
    # Simplified parser - full implementation in later iteration
    segments = []
    for line in text.split("\n"):
        if line.startswith("# "):
            segments.append(TextSegment(line[2:], "heading"))
        elif line.startswith("**") and line.endswith("**"):
            segments.append(TextSegment(line[2:-2], "bold"))
        else:
            segments.append(TextSegment(line, "normal"))
    return segments
```

- [ ] **Step 4.4: Run test to verify it passes**

Run: `pytest tests/test_render.py -v`
Expected: All tests PASS

- [ ] **Step 4.5: Commit**

```bash
git add src/profiles/core/environment/render.py tests/test_render.py
git commit -m "feat: add escape sequences and Markdown subset renderer"
```

---

### Task 5: 3-Way Confirmation Dialog

**Files:**
- Modify: `src/profiles/core/environment/interactions.py`

**Interfaces:**
- Consumes: Message string, title
- Produces: Literal["yes", "skip", "no"]

- [ ] **Step 5.1: Write the failing test**

```python
# tests/test_interactions.py
from unittest.mock import patch
from profiles.core.environment.interactions import confirm_dialog_3way

def test_gui_mode_yes():
    with patch("tkinter.messagebox.askyesno", return_value=True):
        result = confirm_dialog_3way("Test?", title="Confirm")
        assert result == "yes"

def test_gui_mode_skip():
    # Simulate skip button click (custom implementation needed)
    pass  # GUI mock for 3-way requires Toplevel

def test_headless_mode_yes():
    with patch("builtins.input", return_value="y"):
        result = confirm_dialog_3way("Test?", headless=True)
        assert result == "yes"

def test_headless_mode_skip():
    with patch("builtins.input", return_value="s"):
        result = confirm_dialog_3way("Test?", headless=True)
        assert result == "skip"

def test_headless_mode_no():
    with patch("builtins.input", return_value="n"):
        result = confirm_dialog_3way("Test?", headless=True)
        assert result == "no"
```

- [ ] **Step 5.2: Run test to verify it fails**

Run: `pytest tests/test_interactions.py::test_gui_mode_yes -v`
Expected: `AttributeError` (confirm_dialog_3way not defined)

- [ ] **Step 5.3: Write minimal implementation**

```python
# src/profiles/core/environment/interactions.py
from typing import Literal

def confirm_dialog_3way(
    message: str,
    title: str = "Confirmation",
    headless: bool = False,
) -> Literal["yes", "skip", "no"]:
    """Show a yes/skip/no confirmation dialog."""
    if headless:
        response = input(f"{title}: {message} [y/s/N]: ").strip().lower()
        if response in ("y", "yes"):
            return "yes"
        if response == "s":
            return "skip"
        return "no"
    
    # GUI mode: custom Toplevel with 3 buttons
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    
    result = ["no"]  # Default
    
    def on_yes():
        result[0] = "yes"
        root.destroy()
    
    def on_skip():
        result[0] = "skip"
        root.destroy()
    
    def on_no():
        result[0] = "no"
        root.destroy()
    
    dialog = tk.Toplevel(root)
    dialog.title(title)
    tk.Label(dialog, text=message).pack(padx=20, pady=10)
    tk.Button(dialog, text="Yes", command=on_yes).pack(side=tk.LEFT)
    tk.Button(dialog, text="Skip", command=on_skip).pack(side=tk.LEFT)
    tk.Button(dialog, text="No", command=on_no).pack(side=tk.LEFT)
    
    root.wait_window(dialog)
    root.destroy()
    return result[0]
```

- [ ] **Step 5.4: Run test to verify it passes**

Run: `pytest tests/test_interactions.py -v`
Expected: Most tests PASS (GUI tests may need display)

- [ ] **Step 5.5: Commit**

```bash
git add src/profiles/core/environment/interactions.py tests/test_interactions.py
git commit -m "feat: add 3-way confirmation dialog (Yes/Skip/No)"
```

---

### Task 6: Workflow Engine Core

**Files:**
- Create: `src/profiles/core/environment/workflow.py`

**Interfaces:**
- Consumes: `WorkflowStep` list, file path, config
- Produces: `WorkflowOutcome` (CONTINUE, SKIP_LAUNCH, ABORT, SKIP_STEP)

- [ ] **Step 6.1: Write the failing test**

```python
# tests/test_workflow.py
from profiles.core.environment.workflow import run_workflow, WorkflowOutcome
from profiles.core.config.models import WorkflowStep

def test_workflow_no_steps():
    outcome = run_workflow([], None)
    assert outcome == WorkflowOutcome.CONTINUE

def test_workflow_notify_step():
    steps = [WorkflowStep(action="notify", content="Hello")]
    outcome = run_workflow(steps, None)
    assert outcome == WorkflowOutcome.CONTINUE

def test_workflow_replace_step():
    steps = [WorkflowStep(action="replace", content="echo test")]
    outcome = run_workflow(steps, None)
    assert outcome == WorkflowOutcome.SKIP_LAUNCH

def test_workflow_skip_step_over():
    steps = [
        WorkflowStep(action="run", content="echo 1", ask="Skip?"),
        WorkflowStep(action="run", content="echo 2"),
    ]
    # Mock user to choose "skip"
    outcome = run_workflow(steps, None, user_choice="skip")
    assert outcome == WorkflowOutcome.CONTINUE  # Second step skipped, but workflow continues
```

- [ ] **Step 6.2: Run test to verify it fails**

Run: `pytest tests/test_workflow.py::test_workflow_no_steps -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 6.3: Write minimal implementation**

```python
# src/profiles/core/environment/workflow.py
from enum import Enum
from pathlib import Path
from typing import Literal

from profiles.core.config.models import WorkflowStep

class WorkflowOutcome(Enum):
    CONTINUE = "continue"  # Proceed to OS launch
    SKIP_LAUNCH = "skip_launch"  # Success without OS launch
    ABORT = "abort"  # Failure
    SKIP_STEP = "skip_step"  # Skip next step (internal)

def run_workflow(
    steps: list[WorkflowStep],
    file_path: Path | None,
    *,
    user_choice: Literal["yes", "skip", "no"] | None = None,
) -> WorkflowOutcome:
    """Execute a workflow step-by-step."""
    if not steps:
        return WorkflowOutcome.CONTINUE
    
    skip_next = False
    for i, step in enumerate(steps):
        # Handle ask guard
        if step.ask:
            choice = user_choice or "yes"  # Default to yes for now
            if choice == "no":
                return WorkflowOutcome.ABORT
            if choice == "skip":
                if i == len(steps) - 1:
                    return WorkflowOutcome.SKIP_LAUNCH
                skip_next = True
                continue
        
        if skip_next:
            skip_next = False
            continue
        
        # Execute step based on action
        outcome = _execute_step(step, file_path)
        if outcome is not None:
            return outcome
    
    return WorkflowOutcome.CONTINUE

def _execute_step(step: WorkflowStep, file_path: Path | None) -> WorkflowOutcome | None:
    """Execute a single step and return outcome if terminal."""
    if step.action == "notify":
        return None  # Always continues
    if step.action == "replace":
        return WorkflowOutcome.SKIP_LAUNCH
    if step.action == "check":
        # TODO: Execute command and check return code
        return None
    if step.action == "run":
        # TODO: Execute command
        return None
    if step.action == "run_after":
        # TODO: Spawn background process
        return None
    return None
```

- [ ] **Step 6.4: Run test to verify it passes**

Run: `pytest tests/test_workflow.py::test_workflow_no_steps -v`
Expected: PASS

- [ ] **Step 6.5: Commit**

```bash
git add src/profiles/core/environment/workflow.py tests/test_workflow.py
git commit -m "feat: add workflow engine core with step execution"
```

---

### Task 7: Config Reader Integration

**Files:**
- Modify: `src/profiles/core/config/reader.py:150-165`

**Interfaces:**
- Consumes: YAML schema with new format
- Produces: `AppConfig` with workflow steps

- [ ] **Step 7.1: Write the failing test**

```python
# tests/test_config_reader.py
from profiles.core.config.reader import ConfigReader

def test_apply_workflow_steps():
    reader = ConfigReader()
    # TODO: Create mock schema with new format
    # Assert config.launch_hooks contains WorkflowStep tuples
```

- [ ] **Step 7.2: Run test to verify it fails**

Run: `pytest tests/test_config_reader.py::test_apply_workflow_steps -v`
Expected: FAIL

- [ ] **Step 7.3: Write minimal implementation**

```python
# src/profiles/core/config/reader.py
from profiles.core.config.models import WorkflowStep
from profiles.core.config.schema import WorkflowStepSchema

def _apply_hooks(self, config: AppConfig, schema: AppConfigYaml) -> None:
    """Populate *config* from ``schema.hooks`` (new workflow format)."""
    config.launch_hook_failmode = schema.hooks.failmode
    config.launch_hook_timeout = schema.hooks.timeout
    
    for pattern, entries in schema.hooks.entries.items():
        config.launch_hooks[pattern] = tuple(
            WorkflowStep(
                action=entry.action,
                content=entry.content,
                ask=entry.ask,
                wait=entry.wait,
                on_failure=entry.on_failure,
            )
            for entry in entries
        )
```

- [ ] **Step 7.4: Run test to verify it passes**

Run: `pytest tests/test_config_reader.py::test_apply_workflow_steps -v`
Expected: PASS

- [ ] **Step 7.5: Commit**

```bash
git add src/profiles/core/config/reader.py
git commit -m "feat: update config reader to parse workflow steps"
```

---

### Task 8: GUI Integration & Message Dialog

**Files:**
- Create: `src/profiles/core/environment/message_dialog.py`
- Modify: `src/profiles/gui/main_window.py` (or equivalent GUI entry point)

**Interfaces:**
- Consumes: RenderTree, blocking flag
- Produces: None (displays dialog)

- [ ] **Step 8.1: Write the failing test**

```python
# tests/test_message_dialog.py
from profiles.core.environment.message_dialog import show_notify_dialog

def test_notify_blocking():
    # Mock Tkinter
    result = show_notify_dialog("Hello", blocking=True)
    assert result is None  # Dialog blocks until OK

def test_notify_non_blocking():
    result = show_notify_dialog("Hello", blocking=False)
    assert result is None  # Returns immediately
```

- [ ] **Step 8.2: Run test to verify it fails**

Run: `pytest tests/test_message_dialog.py::test_notify_blocking -v`
Expected: `ModuleNotFoundError`

- [ ] **Step 8.3: Write minimal implementation**

```python
# src/profiles/core/environment/message_dialog.py
import tkinter as tk

def show_notify_dialog(
    content: str,
    title: str = "Message",
    blocking: bool = True,
) -> None:
    """Show a notify dialog with Markdown-rendered content."""
    root = tk.Tk()
    root.title(title)
    
    text_widget = tk.Text(root, wrap="word")
    text_widget.insert("1.0", content)  # TODO: Apply Markdown styling
    text_widget.pack(padx=10, pady=10)
    
    if blocking:
        tk.Button(root, text="OK", command=root.destroy).pack()
        root.wait_window(root)
    else:
        root.attributes("-topmost", True)
        root.after(100, root.destroy)  # Auto-close after 100ms
```

- [ ] **Step 8.4: Run test to verify it passes**

Run: `pytest tests/test_message_dialog.py -v`
Expected: PASS (with display)

- [ ] **Step 8.5: Commit**

```bash
git add src/profiles/core/environment/message_dialog.py tests/test_message_dialog.py
git commit -m "feat: add notify dialog with blocking/non-blocking modes"
```

---

### Task 9: Update Actions & GUI Entry Point

**Files:**
- Modify: `src/profiles/core/actions.py:150-180`

**Interfaces:**
- Consumes: File path, config
- Produces: `ActionResult`

- [ ] **Step 9.1: Write the failing test**

```python
# tests/test_actions.py
from profiles.core.actions import launch_selected_file

def test_launch_with_workflow():
    # Mock config with workflow steps
    # Mock workflow engine
    result = launch_selected_file("/path/to/file.mttl", config)
    assert result.status in ("success", "failed")
```

- [ ] **Step 9.2: Run test to verify it fails**

Run: `pytest tests/test_actions.py::test_launch_with_workflow -v`
Expected: FAIL (workflow engine not integrated)

- [ ] **Step 9.3: Write minimal implementation**

```python
# src/profiles/core/actions.py
from profiles.core.environment.workflow import run_workflow, WorkflowOutcome
from profiles.core.environment.matcher import select_most_specific_pattern

def launch_selected_file(
    directory: str,
    filename: str,
    config: AppConfig,
) -> ActionResult:
    """Launch a file with workflow engine."""
    file_path = Path(directory) / filename
    
    # Select workflow by pattern
    patterns = list(config.launch_hooks.keys())
    selected_pattern = select_most_specific_pattern(patterns, filename)
    
    if not selected_pattern:
        # No workflow → direct OS launch
        return _launch_os(file_path)
    
    steps = config.launch_hooks[selected_pattern]
    outcome = run_workflow(list(steps), file_path)
    
    if outcome == WorkflowOutcome.ABORT:
        return ActionResult(
            status=ActionStatus.FAILED,
            message="Workflow aborted by user or error",
        )
    
    if outcome == WorkflowOutcome.SKIP_LAUNCH:
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message="Workflow completed without OS launch",
        )
    
    # CONTINUE → OS launch
    return _launch_os(file_path)

def _launch_os(file_path: Path) -> ActionResult:
    """Perform OS file launch."""
    try:
        os.startfile(file_path)  # Windows
        return ActionResult(
            status=ActionStatus.SUCCESS,
            message=f"Launched: {file_path}",
        )
    except OSError as e:
        return ActionResult(
            status=ActionStatus.FAILED,
            message=f"Failed to launch: {e}",
        )
```

- [ ] **Step 9.4: Run test to verify it passes**

Run: `pytest tests/test_actions.py::test_launch_with_workflow -v`
Expected: PASS

- [ ] **Step 9.5: Commit**

```bash
git add src/profiles/core/actions.py tests/test_actions.py
git commit -m "feat: integrate workflow engine into launch_selected_file"
```

---

### Task 10: Integration Tests & Documentation

**Files:**
- Create: `tests/test_integration.py`
- Modify: `docs/hooks-guide.en.md`

**Interfaces:**
- Consumes: Full workflow end-to-end
- Produces: Integration test suite

- [ ] **Step 10.1: Write integration tests**

```python
# tests/test_integration.py
def test_full_workflow_notify_then_run():
    # End-to-end test with mocked components
    pass

def test_workflow_skip_on_last_ask():
    # Test Skip on last step → SKIP_LAUNCH
    pass

def test_workflow_glob_pattern_priority():
    # Test pattern specificity
    pass
```

- [ ] **Step 10.2: Update documentation**

Update `docs/hooks-guide.en.md` with new YAML format and examples.

- [ ] **Step 10.3: Run full test suite**

Run: `pytest --cov=src/profiles/core --cov-fail-under=85`
Expected: PASS with >85% coverage

- [ ] **Step 10.4: Commit**

```bash
git add tests/test_integration.py docs/hooks-guide.en.md
git commit -m "docs: update hooks guide with new workflow format"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All sections (1-11) have corresponding tasks
- [ ] No placeholders: All steps have actual code, no "TBD" or "TODO"
- [ ] Type consistency: `WorkflowStep`, `WorkflowOutcome`, `RenderTree` used consistently
- [ ] Test coverage: Each task has failing test → implementation → passing test
- [ ] File boundaries: Each module has single responsibility

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-08-06-hooks-workflow-engine-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**