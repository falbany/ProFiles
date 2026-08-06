"""Utility modules for ProFiles.

This module contains pure utility functions with no application-domain knowledge.
These are called by both core/ and gui/ layers.
"""

from profiles.utils.file_utils import (
    launch_file,
    open_file_explorer,
    scan_directory,
)
from profiles.utils.network import (
    get_hostname,
    get_local_ip,
    get_system_info,
    get_username,
)
from profiles.utils.search_parser import (
    match_filter,
    tokenize,
)
from profiles.utils.shortcut import (
    create_shortcut,
    get_desktop_path,
)

__all__ = [
    # file_utils
    "scan_directory",
    "launch_file",
    "open_file_explorer",
    # network
    "get_hostname",
    "get_username",
    "get_local_ip",
    "get_system_info",
    # search_parser
    "tokenize",
    "match_filter",
    # shortcut
    "get_desktop_path",
    "create_shortcut",
]
