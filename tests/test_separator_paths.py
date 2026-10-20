"""Stems go under cache_dir, never beside the audio file or into a show folder."""

import sys
import types
from pathlib import Path

import pytest

from xlights_mcp.audio import separator
from xlights_mcp.config import ServerConfig


@pytest.fixture
def fake_demucs(monkeypatch):
    for name in ("torch", "demucs", "demucs.separate"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))


def _cfg(show):
    return ServerConfig(show_folders={"s": str(show)})


def test_stem_dir_is_under_cache_not_audio_dir(tmp_path):
    audio = tmp_path / "music" / "Song.mp3"
    d = separator.stem_dir_for(audio, tmp_path / "cache")
    assert d.parent == tmp_path / "cache"
    assert not d.is_relative_to(audio.parent)


def test_same_name_different_dirs_do_not_collide(tmp_path):
    a = separator.stem_dir_for(tmp_path / "a" / "S.mp3", tmp_path / "c")
    b = separator.stem_dir_for(tmp_path / "b" / "S.mp3", tmp_path / "c")
    assert a != b


def test_refuses_cache_inside_show_folder(tmp_path, monkeypatch, fake_demucs):
    show = tmp_path / "show"
    show.mkdir()
    monkeypatch.setattr("xlights_mcp.config.load_config", lambda: _cfg(show))
    audio = tmp_path / "S.mp3"
    audio.write_bytes(b"x")
    out = separator.separate_stems(audio, cache_dir=show / "cache")
    assert out.available is False
    assert not (show / "cache").exists()
    assert not (tmp_path / "stems").exists()


def test_refuses_cache_in_drive(tmp_path, monkeypatch, fake_demucs):
    monkeypatch.setattr("xlights_mcp.config.load_config", lambda: ServerConfig())
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    audio = tmp_path / "S.mp3"
    audio.write_bytes(b"x")
    out = separator.separate_stems(audio, cache_dir=tmp_path / "My Drive" / "c")
    assert out.available is False
    assert not (tmp_path / "My Drive").exists()
