"""Network utilities for ProFiles.

Provides functions to retrieve local system information such as
hostname, IP address, and username.
"""

from __future__ import annotations

import getpass
import platform
import socket


def get_hostname() -> str:
    """Get the local machine's hostname.

    Returns:
        The hostname as a string, upper-cased.
    """
    return platform.node().upper()


def get_username() -> str:
    """Get the current user's login name.

    Returns:
        The username string.
    """
    return getpass.getuser()


def get_local_ip() -> str:
    """Get the local machine's non-loopback IPv4 address.

    Attempts to connect to a public DNS server to determine the
    outbound interface IP, falling back to hostname resolution.

    Returns:
        The IP address string, or 'Unknown' if it cannot be determined.
    """
    try:
        # Connect to a public DNS to get the outbound interface IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1.0)
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and ip != "127.0.0.1":
                return ip
    except OSError:
        pass

    # Fallback: iterate through all interfaces
    try:
        hostname = socket.gethostname()
        for addr_info in socket.getaddrinfo(hostname, None):
            ip = addr_info[4][0]
            if isinstance(ip, str) and not ip.startswith("127.") and "." in ip:
                return ip
    except (socket.gaierror, OSError):
        pass

    return "Unknown"


def get_system_info() -> dict:
    """Get a dictionary of local system information.

    Returns:
        Dict with keys: 'hostname', 'username', 'ip_address', 'os'.
    """
    return {
        "hostname": get_hostname(),
        "username": get_username(),
        "ip_address": get_local_ip(),
        "os": platform.platform(),
    }
