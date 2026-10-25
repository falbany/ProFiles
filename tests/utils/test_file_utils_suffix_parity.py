"""Parity tests for ``suffix_of_name`` — Task 7.

``suffix_of_name`` must equal ``"".join(Path(name).suffixes)`` for every
corpus name (the pipeline references Path behavior; users see its
results). Corpus deliberately includes dotfiles, trailing dots and odd
double-dot shapes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from profiles.utils.file_utils import suffix_of_name

CORPUS = [
    "a.pdf",
    "a.mttx.lnk",
    "README",
    ".bashrc",
    "report.",
    "..x",
    "a..b",
    "file.tar.gz",
    "Scan Me.PDF",
    "x. y.pdf",
    "~$lock.docx",
    "émoji.ñ.txt",
    "a.b c.pdf",
    "",
    ".pdf",
    "..a.b",
    ".a.b",
]


@pytest.mark.parametrize("name", CORPUS)
def test_suffix_of_name_matches_pathlib(name: str) -> None:
    assert suffix_of_name(name) == "".join(Path(name).suffixes)
