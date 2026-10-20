"""FPP is off by default, never touches the network when off, and escapes names."""

from pathlib import Path

import httpx
import pytest

from xlights_mcp.config import FPPConfig, ServerConfig
from xlights_mcp.fpp import client, upload


@pytest.fixture
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(httpx, "get", boom)
    monkeypatch.setattr(httpx, "post", boom)


def test_disabled_by_default():
    assert FPPConfig().enabled is False
    assert ServerConfig().fpp.enabled is False


def test_disabled_config_without_enabled_key():
    assert ServerConfig.model_validate({"fpp": {"host": "x"}}).fpp.enabled is False


def test_disabled_blocks_every_client_call(no_network):
    cfg = FPPConfig()
    for result in (
        client.get_fpp_status(cfg),
        client.list_playlists(cfg),
        client.start_playlist(cfg, "a"),
        client.stop_playback(cfg),
    ):
        assert "disabled" in result["error"]


def test_disabled_blocks_upload(no_network, tmp_path):
    f = tmp_path / "a.fseq"
    f.write_bytes(b"x")
    assert "disabled" in upload.upload_sequence(FPPConfig(), f)["error"]


def test_playlist_name_is_escaped(monkeypatch):
    seen = []
    monkeypatch.setattr(client, "_get", lambda c, p: seen.append(p) or {})
    client.start_playlist(FPPConfig(enabled=True), "../../x?y")
    assert seen == ["/playlist/..%2F..%2Fx%3Fy/start/0"]


def test_upload_rejects_non_fseq_and_bad_audio(no_network, tmp_path):
    cfg = FPPConfig(enabled=True)
    secret = tmp_path / "id_rsa"
    secret.write_text("k")
    assert "fseq" in upload.upload_sequence(cfg, secret)["error"]
    f = tmp_path / "a.fseq"
    f.write_bytes(b"x")
    assert "audio" in upload.upload_sequence(cfg, f, secret)["error"].lower()
