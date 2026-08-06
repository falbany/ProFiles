"""Tests for profiles.utils.network — hostname, username, IP, system_info."""

from __future__ import annotations

import socket

from profiles.utils.network import get_hostname, get_local_ip, get_system_info, get_username


class TestGetHostname:
    """get_hostname returns uppercase hostname."""

    def test_returns_uppercase(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("platform.node", return_value="my-pc")
        assert get_hostname() == "MY-PC"

    def test_returns_uppercase_already_upper(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("platform.node", return_value="SERVER-01")
        assert get_hostname() == "SERVER-01"

    def test_empty_hostname(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("platform.node", return_value="")
        assert get_hostname() == ""


class TestGetUsername:
    """get_username returns current user."""

    def test_returns_username(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("getpass.getuser", return_value="jdoe")
        assert get_username() == "jdoe"

    def test_empty_username(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("getpass.getuser", return_value="")
        assert get_username() == ""


class TestGetLocalIp:
    """get_local_ip — primary path, fallback, and Unknown."""

    def _make_socket_mock(self, mocker):  # type: ignore[no-untyped-def]
        """Create a socket mock configured to work as a context manager.

        The ``with socket.socket(...) as sock:`` pattern calls ``__enter__``,
        which by default returns a *different* MagicMock.  We override it
        to return the same object so all configured attributes are visible.
        """
        mock_sock = mocker.MagicMock()
        mock_sock.__enter__.return_value = mock_sock
        return mock_sock

    def test_primary_path_returns_ip(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Socket connect + getsockname succeeds with non-loopback IP."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.getsockname.return_value = ("10.0.0.5", 0)
        mocker.patch("socket.socket", return_value=mock_sock)
        ip = get_local_ip()
        assert ip == "10.0.0.5"
        mock_sock.connect.assert_called_once_with(("8.8.8.8", 80))

    def test_primary_returns_loopback_uses_fallback(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Primary returns 127.0.0.1, fallback via getaddrinfo succeeds."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.getsockname.return_value = ("127.0.0.1", 0)
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, 0, 0, "", ("192.168.1.10", 0))],
        )

        ip = get_local_ip()
        assert ip == "192.168.1.10"

    def test_primary_oserror_fallback_succeeds(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Primary socket raises OSError, fallback via getaddrinfo works."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.connect.side_effect = OSError("no network")
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, 0, 0, "", ("10.0.0.1", 0))],
        )

        ip = get_local_ip()
        assert ip == "10.0.0.1"

    def test_all_fail_returns_unknown(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Both primary and fallback fail."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.connect.side_effect = OSError("no network")
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch("socket.getaddrinfo", side_effect=socket.gaierror("no address"))

        ip = get_local_ip()
        assert ip == "Unknown"

    def test_primary_exception_fallback_ipv6_skipped(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Fallback returns IPv6 addresses, which should be skipped (dotted check)."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.connect.side_effect = OSError("fail")
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch(
            "socket.getaddrinfo",
            return_value=[
                (socket.AF_INET6, 0, 0, "", ("::1", 0, 0, 0)),
                (socket.AF_INET, 0, 0, "", ("10.0.0.1", 0)),
            ],
        )
        ip = get_local_ip()
        assert ip == "10.0.0.1"

    def test_fallback_getaddrinfo_oserror(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Fallback getaddrinfo raises OSError."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.connect.side_effect = OSError("fail")
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch("socket.getaddrinfo", side_effect=OSError("no addr"))
        ip = get_local_ip()
        assert ip == "Unknown"

    def test_primary_getsockname_returns_empty(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Primary path: getsockname returns empty string."""
        mock_sock = self._make_socket_mock(mocker)
        mock_sock.getsockname.return_value = ("", 0)
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, 0, 0, "", ("10.0.0.1", 0))],
        )
        ip = get_local_ip()
        assert ip == "10.0.0.1"

    def test_primary_timeout(self, mocker) -> None:  # type: ignore[no-untyped-def]
        """Socket timeout is set to 1.0."""
        mock_sock = self._make_socket_mock(mocker)
        mocker.patch("socket.socket", return_value=mock_sock)
        mocker.patch(
            "socket.getaddrinfo",
            return_value=[(socket.AF_INET, 0, 0, "", ("10.0.0.1", 0))],
        )
        get_local_ip()
        mock_sock.settimeout.assert_called_once_with(1.0)


class TestGetSystemInfo:
    """get_system_info returns dict with keys."""

    def test_returns_all_keys(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.utils.network.get_hostname", return_value="HOST")
        mocker.patch("profiles.utils.network.get_username", return_value="user")
        mocker.patch("profiles.utils.network.get_local_ip", return_value="1.2.3.4")
        mocker.patch("platform.platform", return_value="Windows-10")

        info = get_system_info()
        assert info == {
            "hostname": "HOST",
            "username": "user",
            "ip_address": "1.2.3.4",
            "os": "Windows-10",
        }

    def test_has_correct_keys(self, mocker) -> None:  # type: ignore[no-untyped-def]
        mocker.patch("profiles.utils.network.get_hostname", return_value="X")
        mocker.patch("profiles.utils.network.get_username", return_value="X")
        mocker.patch("profiles.utils.network.get_local_ip", return_value="X")
        mocker.patch("platform.platform", return_value="X")

        info = get_system_info()
        assert set(info.keys()) == {"hostname", "username", "ip_address", "os"}
