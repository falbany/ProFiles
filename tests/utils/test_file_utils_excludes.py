"""Exclude-pattern compilation tests — Task 8.

Glob semantics must be preserved exactly (language = ``fnmatch``,
matching case-insensitively); the compiler is memoized
(``lru_cache(maxsize=64)``) and builds one combined regex.
"""

from __future__ import annotations

import pytest

from profiles.utils.file_utils import _compile_excludes, _is_excluded


class TestGlobSemantics:
    """Behavior parity with the per-pattern fnmatch loop."""

    @pytest.mark.parametrize(
        ("name", "patterns", "expected"),
        [
            ("debug_out", ("Debug*",), True),
            ("Debug_out", ("Debug*",), True),
            ("a.tmp", ("*.TMP",), True),
            ("a.tmp2", ("*.TMP",), False),
            ("ax", ("[ab]x",), True),
            ("bx", ("[ab]x",), True),
            ("cx", ("[ab]x",), False),
            (
                "~$lock.docx",
                ("~$*",),
                True,
            ),  # `$` is literal in fnmatch
            ("lock.docx", ("~$*",), False),
            ("anything", (), False),
            ("file", ("file",), True),
            ("files", ("file",), False),
            ("x", ("?",), True),
            ("xy", ("?",), False),
        ],
    )
    def test_is_excluded_semantics(
        self, name: str, patterns: tuple[str, ...], expected: bool
    ) -> None:
        assert _is_excluded(name, patterns) is expected

    def test_multiple_patterns_any_match(self) -> None:
        assert _is_excluded("a.tmp", (".git", "*.TMP")) is True
        assert _is_excluded("keep.pdf", (".git", "*.TMP")) is False


class TestCompileExcludes:
    """The compiled predicate: single regex, memoized."""

    def test_returns_callable_with_same_semantics(self) -> None:
        matcher = _compile_excludes(("Debug*", "~$*"))
        assert callable(matcher)
        assert matcher("Debug_out") is True
        assert matcher("~$lock.docx") is True
        assert matcher("keep.pdf") is False

    def test_is_cached(self) -> None:
        key = tuple(["a", "b"])
        _compile_excludes.cache_clear()
        _compile_excludes(key)
        info_before = _compile_excludes.cache_info()
        _compile_excludes(key)  # second call → cache hit
        info_after = _compile_excludes.cache_info()
        assert info_after.hits == info_before.hits + 1

    def test_empty_patterns_match_nothing(self) -> None:
        matcher = _compile_excludes(())
        assert matcher("anything") is False

    def test_case_insensitive(self) -> None:
        matcher = _compile_excludes(("Debug*",))
        assert matcher("DEBUG_OUT") is True
        assert matcher("node_modules") is False
