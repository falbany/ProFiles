"""Hook-step ``if:`` condition grammar — pure evaluation, no token logic.

Single Responsibility: evaluate one already-substituted condition string.
Token substitution happens in the workflow engine *before* this module is
called, so conditions never see ``{{token}}`` placeholders.

Grammar (a strict prefix grammar — the remainder after the prefix is literal):

    env:VAR          true when VAR is set (any value)
    env:VAR=value    true when VAR is set and equals value
    env:VAR!=value   true when VAR is set and differs from value
    file:PATH        true when PATH exists (file or directory)
    !COND            negation of COND (composes with every form above)

Empty / whitespace-only conditions are treated as unset (always true).
Unrecognized syntax evaluates to false and emits a debug log — the step
is skipped, but the reason is no longer silent.
"""

from __future__ import annotations

import logging
import os

_LOGGER = logging.getLogger(__name__)

_ENV_PREFIX = "env:"
_FILE_PREFIX = "file:"
_NEGATION_PREFIX = "!"


def _evaluate_env(body: str) -> bool:
    """Evaluate an ``env:`` body (everything after the prefix)."""
    # ``!=`` must be tested before ``=``: partition on ``=`` would
    # split ``VAR!=value`` into name ``VAR!`` / expected ``=value``.
    if "!=" in body:
        name, _, expected = body.partition("!=")
        actual = os.environ.get(name)
        return actual is not None and actual != expected
    if "=" in body:
        name, _, expected = body.partition("=")
        actual = os.environ.get(name)
        return actual is not None and actual == expected
    return os.environ.get(body) is not None


def evaluate_hook_condition(condition: str | None) -> bool:
    """Evaluate a hook-step ``if:`` condition string.

    Args:
        condition: The condition to evaluate (already token-substituted).
            ``None`` or whitespace-only means "no condition" (always true).

    Returns:
        True when the condition holds. Unrecognized syntax returns False
        (the step is skipped) and logs a debug message.
    """
    if condition is None or not condition.strip():
        return True
    cond = condition.strip()

    if cond.startswith(_NEGATION_PREFIX):
        return not evaluate_hook_condition(cond[len(_NEGATION_PREFIX) :])

    if cond.startswith(_FILE_PREFIX):
        return os.path.exists(cond[len(_FILE_PREFIX) :])

    if cond.startswith(_ENV_PREFIX):
        return _evaluate_env(cond[len(_ENV_PREFIX) :])

    _LOGGER.debug("Unrecognized hook condition (step skipped): %r", condition)
    return False


__all__ = ["evaluate_hook_condition"]
