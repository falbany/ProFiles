"""Tests for notify message dialog."""

from profiles.core.environment.message_dialog import show_notify_dialog

def test_notify_headless_mode(capsys):
    show_notify_dialog("Hello **world**", title="Info", headless=True)
    captured = capsys.readouterr()
    assert "[Info] Hello world" in captured.out

def test_notify_non_blocking_headless(capsys):
    show_notify_dialog("Test message", blocking=False, headless=True)
    captured = capsys.readouterr()
    assert "Test message" in captured.out
