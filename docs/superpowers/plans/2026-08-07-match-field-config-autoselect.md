# Implementation Plan: `match` Field Config Auto-Selection & Multi-Directory Scanning

**Spec File:** `docs/superpowers/specs/2026-08-07-match-field-config-autoselect-design.md`  
**Plan File:** `docs/superpowers/plans/2026-08-07-match-field-config-autoselect.md`  

---

## File Structure & Responsibilities

- `src/profiles/core/config/schema.py`: Pydantic models for `MatchCriteriaSchema` and `MachineConfig` (`match` & `scan: list[str]`).
- `src/profiles/core/config/models.py`: Frozen dataclass models `MatchCriteria` and updated `MachineConfiguration` (`match` & `scan: tuple[str, ...]`).
- `src/profiles/core/config/matcher.py` *(New)*: Core pattern evaluation and config selection logic (`match_pattern`, `matches_machine_config`, `select_active_configuration`).
- `src/profiles/core/config/service.py`: Service functions updated to delegate configuration matching and directory auto-selection to `matcher.py`.
- `src/profiles/core/scanner.py`: High-performance multi-directory scanner pipeline supporting `scan: tuple[str, ...]`.
- `tests/test_config_matcher.py` *(New)*: Unit tests for pattern matching and configuration selection across cross-platform path formats.
- `tests/test_scanner.py`: Updated unit tests verifying multi-directory scanning and path deduplication.

---

## Task List

### Task 1: Update Configuration Schema & Dataclass Models (TDD)
- [ ] Write failing test in `tests/test_config_schema.py` validating `MatchCriteriaSchema`, list coercion, and `scan: list[str]` in `MachineConfig`.
- [ ] Update `src/profiles/core/config/schema.py` with `MatchCriteriaSchema` and updated `MachineConfig`.
- [ ] Update `src/profiles/core/config/models.py` with `MatchCriteria` and updated `MachineConfiguration`.
- [ ] Run tests to verify schema parsing and model coercion pass.
- [ ] Commit changes with message `feat(config): add MatchCriteria schema and models`.

### Task 2: Implement Pattern Matcher & Config Selection Engine (TDD)
- [ ] Write failing tests in `tests/test_config_matcher.py` for glob, regex (`re:`), path normalization, OR evaluation logic, and OS cross-platform matching.
- [ ] Implement `src/profiles/core/config/matcher.py` with `match_pattern`, `matches_machine_config`, and `select_active_configuration`.
- [ ] Update `src/profiles/core/config/service.py` to use `matcher.py`.
- [ ] Run unit tests to verify all matching tests pass.
- [ ] Commit changes with message `feat(config): implement pattern matcher and selection engine`.

### Task 3: Multi-Directory High-Performance Scanning (TDD)
- [ ] Write failing tests in `tests/test_scanner.py` verifying multi-directory input scanning and deduplication across overlapping paths.
- [ ] Update `src/profiles/core/scanner.py` to accept multiple scan directories and perform deduplication by resolved path.
- [ ] Run all tests and verify scanner performance.
- [ ] Commit changes with message `feat(scanner): add multi-directory scanning and deduplication`.

### Task 4: System Integration & Verification
- [ ] Update GUI/App startup logic in `src/profiles/app.py` and `src/profiles/gui/main_window.py` to use `match` and `scan`.
- [ ] Run pytest suite across the workspace.
- [ ] Commit integration updates with message `feat(app): integrate match and scan config autoselect`.
