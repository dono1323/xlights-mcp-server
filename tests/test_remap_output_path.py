"""Remap output names stay inside the show folder and never overwrite."""

from xlights_mcp.remapper.generator import next_remapped_path, sanitize_base_name


def test_traversal_title_stays_inside(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    p = next_remapped_path("../../My Drive/xLights (1)/Christmas Show/x", show)
    assert p.parent == show
    assert "/" not in p.name


def test_bracket_title_counts_existing(tmp_path):
    (tmp_path / "Carol [Remix] (remapped 1).xsq").write_text("x")
    p = next_remapped_path("Carol [Remix]", tmp_path)
    assert p.name == "Carol [Remix] (remapped 2).xsq"


def test_skips_existing_file_even_if_pattern_misses(tmp_path):
    (tmp_path / "A (remapped 1).xsq").write_text("x")
    (tmp_path / "A (remapped 2).xsq").write_text("x")
    assert next_remapped_path("A", tmp_path).name == "A (remapped 3).xsq"


def test_sanitize():
    assert sanitize_base_name("") == "Sequence"
    assert sanitize_base_name("..") == "Sequence"
    assert sanitize_base_name("a\\b:c") == "a_b_c"
