"""Tests for the config editor endpoints: validate + content + save + save-as."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from profiles.core.config.models import AppConfig
from profiles.core.config.reader import ConfigReader
from profiles.core.config.template import STARTER_CONFIG_TEMPLATE
from profiles.server.app import create_app
from profiles.server.routes.config import has_disk_path, validate_issues
from profiles.server.state import ServerState


@pytest.fixture
def config_state(tmp_path: Path) -> ServerState:
    config = AppConfig(
        title="Editor Session",
        search_dir=str(tmp_path),
        extensions=(".txt",),
    )
    config.config_path = tmp_path / ".profiles"
    return ServerState(config=config, active_directory=tmp_path)


@pytest.mark.anyio
async def test_validate_returns_valid_true_for_starter_template(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Verify a freshly rendered starter template validates with no issues."""
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/validate",
            json={
                "content": STARTER_CONFIG_TEMPLATE.format(cwd=str(tmp_path)),
                "filename": ".profiles",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"valid": True, "issues": []}


@pytest.mark.anyio
async def test_validate_returns_issues_for_bad_yaml(config_state: ServerState) -> None:
    """Verify invalid YAML yields a valid=False payload with an error issue."""
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/validate",
            json={"content": "defaults: [unclosed", "filename": ".profiles"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is False
    assert payload["issues"][0]["severity"] == "error"
    assert payload["issues"][0]["message"]


@pytest.mark.anyio
async def test_validate_does_not_change_state(config_state: ServerState) -> None:
    """Verify validation is read-only: the live configuration is untouched."""
    original = config_state.config
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/validate",
            json={"content": "defaults: [unclosed", "filename": ".profiles"},
        )

    assert response.status_code == 200
    assert config_state.config is original


@pytest.mark.anyio
async def test_content_returns_active_config_text(tmp_path: Path) -> None:
    """Verify GET /content returns the on-disk text of the active config file."""
    config_path = tmp_path / ".profiles"
    file_text = 'version: 1\ndefaults:\n  title: "On Disk"\n'
    config_path.write_text(file_text, encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == file_text
    assert payload["filename"] == ".profiles"
    assert payload["config_path"] == str(config_path)
    assert payload["session_trial"] is False


@pytest.mark.anyio
async def test_content_flags_session_trial(tmp_path: Path) -> None:
    """Verify a config with no recorded disk path is reported as a session trial."""
    config = AppConfig(
        title="Trial Session",
        search_dir=str(tmp_path),
        extensions=(".txt",),
    )
    # A config applied from dropped content carries no recorded disk path:
    # neither the state nor the AppConfig tracks the file it came from.
    config.config_path = None
    state = ServerState(config=config, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_trial"] is True
    assert payload["config_path"] is None


@pytest.mark.anyio
async def test_content_flags_session_trial_after_live_drop(
    config_state: ServerState,
) -> None:
    """Pin the live flow: a dropped config must never expose a disk anchor.

    Ruling R4: ``_config_response`` re-records a resolved path into the
    state even for a drop, so trial detection must ride the explicit
    ``ServerState.session_trial`` flag — not path absence.

    The endpoint echoes the applied YAML text (issue #97): an editor
    reopened after an Apply must show the live in-memory configuration,
    not an empty body.
    """
    trial_text = "defaults:\n  title: Dropped\n  extensions:\n    - .mttl\n"
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        drop = await client.post(
            "/api/config/load-content",
            json={"filename": "my.profiles", "content": trial_text},
        )
        assert drop.status_code == 200
        assert drop.json()["session_trial"] is True

        assert has_disk_path(config_state) is False

        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_trial"] is True
    assert payload["config_path"] is None
    assert payload["filename"] == "Dropped"
    assert payload["content"] == trial_text


@pytest.mark.anyio
async def test_content_returns_disk_text_after_trial_is_anchored(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Verify anchoring the session to disk clears the stored trial text.

    Given: A session holding a session-trial config (applied content)
    When: POST /load anchors a real disk config file
    Then: GET /content returns the disk file text with session_trial
        cleared — the trial content is dropped, never leaked into the
        disk-anchored response
    """
    disk_path = tmp_path / ".profiles"
    disk_text = 'defaults:\n  title: "On Disk"\n'
    disk_path.write_text(disk_text, encoding="utf-8")

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        drop = await client.post(
            "/api/config/load-content",
            json={"filename": "my.profiles", "content": "defaults:\n  title: Dropped\n"},
        )
        assert drop.status_code == 200

        load = await client.post("/api/config/load", json={"config_path": str(disk_path)})
        assert load.status_code == 200

        response = await client.get("/api/config/content")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_trial"] is False
    assert payload["config_path"] == str(disk_path)
    assert payload["content"] == disk_text


@pytest.mark.anyio
async def test_content_for_missing_file_returns_text_or_error(
    config_state: ServerState,
) -> None:
    """Pinned behavior: a recorded-but-deleted config file answers 404."""
    missing_path = config_state.active_config_path()
    assert not missing_path.exists()

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/config/content")

    assert response.status_code == 404
    assert str(missing_path) in response.json()["detail"]


@pytest.mark.anyio
async def test_save_refused_for_session_trial(config_state: ServerState, tmp_path: Path) -> None:
    """Verify save is refused (400) for a session trial and writes nothing.

    Given: A config applied from dropped content (no disk anchor)
    When: POST /save is called
    Then: 400 is returned and no file appears on disk
    """
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        drop = await client.post(
            "/api/config/load-content",
            json={"filename": "my.profiles", "content": "defaults:\n  title: Dropped\n"},
        )
        assert drop.status_code == 200
        assert has_disk_path(config_state) is False

        response = await client.post(
            "/api/config/save",
            json={"content": "defaults:\n  title: Saved\n"},
        )

    assert response.status_code == 400
    assert not (tmp_path / ".profiles").exists()


@pytest.mark.anyio
async def test_save_rejects_invalid_content_without_writing(tmp_path: Path) -> None:
    """Verify invalid content answers 400 with the issues list, file bytes unchanged.

    Given: A disk-anchored session with an on-disk config file
    When: POST /save is called with invalid YAML and no force flag
    Then: 400 with the issues list and the file bytes are untouched
    """
    config_path = tmp_path / ".profiles"
    file_text = 'defaults:\n  title: "On Disk"\n'
    config_path.write_text(file_text, encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save",
            json={"content": "defaults: [unclosed"},
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["severity"] == "error"
    assert detail[0]["message"]
    assert config_path.read_text(encoding="utf-8") == file_text


@pytest.mark.anyio
async def test_save_force_writes_invalid_content(tmp_path: Path) -> None:
    """Verify force=True writes invalid content to disk and answers SAVED.

    Given: A disk-anchored session and invalid YAML content
    When: POST /save is called with force=True
    Then: 200 SAVED and the file contains the invalid text verbatim
    """
    config_path = tmp_path / ".profiles"
    config_path.write_text('defaults:\n  title: "On Disk"\n', encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)
    invalid_text = "defaults: [unclosed"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save",
            json={"content": invalid_text, "force": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(config_path)
    assert config_path.read_text(encoding="utf-8") == invalid_text
    assert "config" in payload


@pytest.mark.anyio
async def test_save_writes_and_applies_valid_config(tmp_path: Path) -> None:
    """Verify a valid save writes the file and applies it to the live state.

    Given: A disk-anchored session and valid YAML content
    When: POST /save is called without force
    Then: 200 SAVED, the file is written, and ``state.config`` reflects
        the new content with the session-trial flag cleared
    """
    config_path = tmp_path / ".profiles"
    config_path.write_text('defaults:\n  title: "Old Title"\n', encoding="utf-8")
    loaded = ConfigReader(config_path).load()
    state = ServerState(config=loaded, active_directory=tmp_path)
    valid_text = f"defaults:\n  title: Fresh Title\n  search_dir: '{tmp_path}'\n"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save",
            json={"content": valid_text},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(config_path)
    assert config_path.read_text(encoding="utf-8") == valid_text
    assert state.config.title == "Fresh Title"
    assert payload["config"]["title"] == "Fresh Title"
    assert state.session_trial is False


@pytest.mark.anyio
async def test_save_as_rejects_filename_with_path_separators(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Verify save-as refuses filenames that could escape the target directory.

    Given: A session and a target directory
    When: POST /save-as is called with a filename containing path
        separators (forward or backslash) or a dot segment
    Then: 400 naming the filename and no file is created anywhere
    """
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for filename in ("sub/../x.profiles", "nested\\x.profiles", "..", ""):
            response = await client.post(
                "/api/config/save-as",
                json={
                    "content": "defaults:\n  title: X\n",
                    "filename": filename,
                    "directory": str(tmp_path),
                },
            )
            assert response.status_code == 400
            assert filename in response.json()["detail"]

    assert not (tmp_path / "x.profiles").exists()
    assert not (tmp_path / "sub").exists()
    assert not (tmp_path / "nested\\x.profiles").exists()


@pytest.mark.anyio
async def test_save_as_rejects_bad_extension(config_state: ServerState, tmp_path: Path) -> None:
    """Verify save-as refuses filenames outside the extension whitelist.

    Given: A session with any active configuration
    When: POST /save-as is called with a ``.yml`` filename
    Then: 400 is returned and no file is created on disk
    """
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": "defaults:\n  title: X\n",
                "filename": "config.yml",
                "directory": str(tmp_path),
            },
        )

    assert response.status_code == 400
    assert not (tmp_path / "config.yml").exists()


@pytest.mark.anyio
async def test_save_as_rejects_existing_target_without_overwrite(tmp_path: Path) -> None:
    """Pin 409 Conflict: an existing target requires overwrite=True.

    Given: A target config file that already exists on disk
    When: POST /save-as targets the same path without overwrite
    Then: 409 is returned naming the path and the file bytes are untouched
    """
    target = tmp_path / ".profiles"
    file_text = 'defaults:\n  title: "Existing"\n'
    target.write_text(file_text, encoding="utf-8")
    loaded = ConfigReader(target).load()
    state = ServerState(config=loaded, active_directory=tmp_path)

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": "defaults:\n  title: Replaced\n",
                "filename": ".profiles",
                "directory": str(tmp_path),
            },
        )

    assert response.status_code == 409
    assert str(target) in response.json()["detail"]
    assert target.read_text(encoding="utf-8") == file_text


@pytest.mark.anyio
async def test_save_as_overwrite_replaces_file(tmp_path: Path) -> None:
    """Verify overwrite=True replaces an existing target with the new content.

    Given: An existing target config file
    When: POST /save-as targets it with overwrite=True and valid content
    Then: 200 SAVED and the file contains the new content verbatim
    """
    target = tmp_path / ".profiles"
    target.write_text('defaults:\n  title: "Old Title"\n', encoding="utf-8")
    loaded = ConfigReader(target).load()
    state = ServerState(config=loaded, active_directory=tmp_path)
    new_text = f"defaults:\n  title: Replaced\n  search_dir: '{tmp_path}'\n"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": new_text,
                "filename": ".profiles",
                "directory": str(tmp_path),
                "overwrite": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(target)
    assert target.read_text(encoding="utf-8") == new_text


@pytest.mark.anyio
async def test_save_as_rejects_invalid_content(tmp_path: Path) -> None:
    """Verify invalid content answers 400 with the issues list and writes nothing.

    Given: A target path with no existing file
    When: POST /save-as is called with invalid YAML and no force flag
    Then: 400 with the issues list and the target file is never created
    """
    target = tmp_path / "draft.profiles"
    state = ServerState(
        config=AppConfig(title="Session", search_dir=str(tmp_path), extensions=(".txt",)),
        active_directory=tmp_path,
    )

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": "defaults: [unclosed",
                "filename": "draft.profiles",
                "directory": str(tmp_path),
            },
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail[0]["severity"] == "error"
    assert detail[0]["message"]
    assert not target.exists()


@pytest.mark.anyio
async def test_save_as_force_saves_invalid_content(tmp_path: Path) -> None:
    """Verify force=True writes invalid content to the new path anyway.

    Given: A target path with no existing file
    When: POST /save-as is called with invalid YAML and force=True
    Then: 200 SAVED and the file contains the invalid text verbatim
    """
    target = tmp_path / "broken.profiles"
    state = ServerState(
        config=AppConfig(title="Session", search_dir=str(tmp_path), extensions=(".txt",)),
        active_directory=tmp_path,
    )
    invalid_text = "defaults: [unclosed"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": invalid_text,
                "filename": "broken.profiles",
                "directory": str(tmp_path),
                "force": True,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(target)
    assert target.read_text(encoding="utf-8") == invalid_text
    assert "config" in payload


@pytest.mark.anyio
async def test_save_as_applies_new_config(tmp_path: Path) -> None:
    """Verify a save-as anchors the session to the new file and re-derives state.

    Given: A session anchored to an existing config and a new valid draft
        whose ``search_dir`` points at a different existing directory
    When: POST /save-as writes the draft to a fresh target path
    Then: 200 SAVED, ``state.config_path`` is the target,
        ``state.active_directory`` is re-derived from the new config, and
        the session-trial flag is cleared
    """
    target = tmp_path / "copy.profiles"
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    old_path = tmp_path / ".profiles"
    old_path.write_text(f"defaults:\n  title: Old\n  search_dir: '{tmp_path}'\n", encoding="utf-8")
    state = ServerState(config=ConfigReader(old_path).load(), active_directory=tmp_path)
    valid_text = f"defaults:\n  title: Saved As Copy\n  search_dir: '{scan_dir}'\n"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": valid_text,
                "filename": "copy.profiles",
                "directory": str(tmp_path),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(target)
    assert target.read_text(encoding="utf-8") == valid_text
    assert state.config_path == target
    assert state.active_directory == scan_dir
    assert state.session_trial is False
    assert payload["config"]["title"] == "Saved As Copy"


@pytest.mark.anyio
async def test_save_as_uppercase_extension_applies_cleanly(tmp_path: Path) -> None:
    """Verify an uppercase save-as target is written AND anchors the session.

    Regression (branch review): the save-as whitelist is case-insensitive —
    ``BACKUP.PROFILES`` passes the extension check and gets written — but
    ``_is_config_path`` compared case-sensitively, so the apply step then
    answered 400 "Not a ProFiles configuration file" for the very file the
    endpoint had just written. The session never anchored, and with
    ``force=True`` invalid YAML could land on disk while the UI reported
    failure.

    Given: A session anchored to an existing config and a valid draft
    When: POST /save-as writes it to ``BACKUP.PROFILES``
    Then: 200 SAVED, the file exists on disk, ``state.config_path`` is the
        target and the session-trial flag is cleared
    """
    target = tmp_path / "BACKUP.PROFILES"
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    old_path = tmp_path / ".profiles"
    old_path.write_text(f"defaults:\n  title: Old\n  search_dir: '{tmp_path}'\n", encoding="utf-8")
    state = ServerState(config=ConfigReader(old_path).load(), active_directory=tmp_path)
    valid_text = f"defaults:\n  title: Upper Backup\n  search_dir: '{scan_dir}'\n"

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/config/save-as",
            json={
                "content": valid_text,
                "filename": "BACKUP.PROFILES",
                "directory": str(tmp_path),
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "SAVED"
    assert payload["path"] == str(target)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == valid_text
    assert state.config_path == target
    assert state.session_trial is False
    assert payload["config"]["title"] == "Upper Backup"


@pytest.mark.anyio
async def test_load_accepts_uppercase_config_filename(tmp_path: Path) -> None:
    """Verify /load accepts a config file named with uppercase extensions.

    Regression (branch review): the same case-sensitive ``_is_config_path``
    gate backs /load, /create and the save apply step, so a valid
    ``MACHINE.PROFILES`` on disk was refused even though the documented
    whitelist (``.profiles`` / ``.profiles.yaml``) is case-insensitive —
    the save-as endpoint itself accepted such names via ``.lower()``.

    Given: A valid config file saved as ``MACHINE.PROFILES``
    When: POST /load is called with its path
    Then: 200, the session swaps to that config and anchors to the file
        (``session_trial`` cleared)
    """
    config_path = tmp_path / "MACHINE.PROFILES"
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    config_path.write_text(
        f"defaults:\n  title: Upper Machine\n  search_dir: '{scan_dir}'\n",
        encoding="utf-8",
    )
    state = ServerState(
        config=AppConfig(title="Before", search_dir=str(tmp_path), extensions=(".txt",)),
        active_directory=tmp_path,
    )

    app = create_app(state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/load", json={"config_path": str(config_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Upper Machine"
    assert state.config_path == config_path
    assert state.session_trial is False


@pytest.mark.anyio
async def test_template_returns_starter_content(config_state: ServerState) -> None:
    """Verify POST /template renders starter content that validates clean.

    Given: A session in any state
    When: POST /template is called
    Then: 200 with filename ".profiles" and content that passes the
        project's own validator (the template has brace-escaping history)
    """
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/template")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == ".profiles"
    assert validate_issues(payload["content"], display_name=".profiles") == []


@pytest.mark.anyio
async def test_template_substitutes_active_directory(
    config_state: ServerState, tmp_path: Path
) -> None:
    """Verify the cwd placeholder is substituted with the active directory."""
    scan_dir = tmp_path / "scans"
    scan_dir.mkdir()
    config_state.active_directory = scan_dir

    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/template")

    assert response.status_code == 200
    search_line = next(
        line
        for line in response.json()["content"].splitlines()
        if line.lstrip().startswith("search_dir:")
    )
    assert str(scan_dir) in search_line


@pytest.mark.anyio
async def test_template_does_not_change_state(config_state: ServerState) -> None:
    """Verify rendering is read-only: the live configuration is untouched."""
    original = config_state.config
    app = create_app(config_state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/config/template")

    assert response.status_code == 200
    assert config_state.config is original
