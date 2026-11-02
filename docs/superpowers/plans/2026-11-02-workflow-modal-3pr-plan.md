# WorkflowRunnerModal — 3-PR improvement plan
Linked issues: #75, #78, #79, #80, #81, #82, #83

> Working in place on a branch (no worktree, per user choice).

## PR 1 — keydown/a11y wiring (current step)
- [ ] **#83** Escape handled twice (hook + window listener) → single close/abort path
      + guard against programmatic double-invoke of `handleClose`
- [ ] **#81** initial focus on the primary action button (status-dependent),
      not the ✕ close button; focus moves on status transitions
- [ ] **#75** footer anchored to the modal bottom (scroll wrapper around content only)

## PR 2 — UX polish
- [ ] **#78** copy-to-clipboard on command/output blocks (extract `CopyButton`)
- [ ] **#82** keyboard shortcuts for decision buttons (Y/N/S, Enter), built on
      the focus utilities from PR 1

## PR 3 — recovery & semantics
- [ ] **#79** session-expired recovery UI (structured error from `api/client.ts`,
      Restart workflow), sidebar error/empty state, error near footer
- [ ] **#80** sidebar list semantics, non-color-only status, roving tabindex,
      aria-live footer hint

## Rules
- One commit per issue, `Fixes #NN` in commit messages.
- Issues close automatically on merge.
- Verify with vitest (`src/profiles/web`) + review against each issue's acceptance criteria.
