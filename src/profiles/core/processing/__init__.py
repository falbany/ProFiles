"""Processing subsystem — file scanning, classification, and column extraction.

- ``scanner``          : directory walker / filter pipeline
- ``column_extractor`` : regex-based dynamic column rules
- ``file_classifier``  : version parsing, file-info validation rules
"""

from __future__ import annotations

from profiles.core.processing.column_extractor import (
    ColumnExtractor,
    ColumnRule,
    load_column_rules_from_config,
)
from profiles.core.processing.file_classifier import (
    directory_exists,
    ensure_trailing_separator,
    extract_version,
    get_file_info,
    get_file_info_dynamic,
)
from profiles.core.processing.scanner import (
    ScannedFile,
    ScannedFileDynamic,
    is_simple_extension,
    scan_and_process,
    scan_and_process_dynamic,
)

__all__ = [
    # Scanner
    "ScannedFile",
    "ScannedFileDynamic",
    "is_simple_extension",
    "scan_and_process",
    "scan_and_process_dynamic",
    # Column extraction
    "ColumnExtractor",
    "ColumnRule",
    "load_column_rules_from_config",
    # File classification
    "directory_exists",
    "ensure_trailing_separator",
    "extract_version",
    "get_file_info",
    "get_file_info_dynamic",
]
