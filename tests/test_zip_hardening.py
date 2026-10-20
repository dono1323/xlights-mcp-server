"""Zip imports can't escape, add xLights XML, or confuse the user's own files."""

import zipfile
from pathlib import Path

from xlights_mcp.remapper.importer import import_package

FIXTURES = Path(__file__).parent / "fixtures" / "remapping"


def _zip(path, extra=()):
    with zipfile.ZipFile(path, "w") as zf:
        zf.write(FIXTURES / "minimal_sequence.xsq", "pack.xsq")
        zf.write(FIXTURES / "minimal_rgbeffects.xml", "xlights_rgbeffects.xml")
        zf.writestr("xlights_networks.xml", "<xlightsNetworks/>")
        for name, data in extra:
            zf.writestr(name, data)


def test_no_xlights_xml_or_xsq_added_to_show(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    z = tmp_path / "p.zip"
    _zip(z, [("pic.png", b"png")])
    _, _, meta, _ = import_package(z, show)
    assert meta is not None
    assert sorted(p.name for p in show.iterdir()) == ["pic.png"]


def test_existing_own_files_are_not_parsed_as_import(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    (show / "xlights_rgbeffects.xml").write_text("<broken")
    (show / "pack.xsq").write_text("<broken")
    z = tmp_path / "p.zip"
    _zip(z)
    seq, _, meta, _ = import_package(z, show)
    assert seq.model_names and meta is not None
    assert (show / "xlights_rgbeffects.xml").read_text() == "<broken"


def test_sibling_prefix_traversal_rejected(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    z = tmp_path / "p.zip"
    _zip(z, [("../Show2/a.png", b"x")])
    import_package(z, show)
    assert not (tmp_path / "Show2").exists()
    assert not (show / "a.png").exists()


def test_existing_asset_not_overwritten(tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    (show / "pic.png").write_bytes(b"mine")
    z = tmp_path / "p.zip"
    _zip(z, [("pic.png", b"theirs")])
    import_package(z, show)
    assert (show / "pic.png").read_bytes() == b"mine"
