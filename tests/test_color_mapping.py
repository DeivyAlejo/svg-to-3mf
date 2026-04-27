from pathlib import Path

import pytest

from svg_to_3mf.color_mapping import ColorMappingError, load_color_mapping, normalize_hex_color


def test_normalize_hex_color_supports_short_and_long_forms() -> None:
    assert normalize_hex_color("#abc") == "#aabbcc"
    assert normalize_hex_color("#AABBCC") == "#aabbcc"


def test_load_color_mapping_accepts_exactly_two_roles() -> None:
    mapping = load_color_mapping(
        '{"#000000":"image","#FF0000":"text"}',
        None,
    )
    assert mapping == {"#000000": "image", "#ff0000": "text"}


def test_load_color_mapping_rejects_missing_role() -> None:
    with pytest.raises(ColorMappingError):
        load_color_mapping('{"#000":"image","#fff":"image"}', None)


def test_load_color_mapping_requires_single_source(tmp_path: Path) -> None:
    file_path = tmp_path / "map.json"
    file_path.write_text('{"#000000":"image","#ff0000":"text"}', encoding="utf-8")

    with pytest.raises(ColorMappingError):
        load_color_mapping(None, None)

    with pytest.raises(ColorMappingError):
        load_color_mapping('{"#000000":"image","#ff0000":"text"}', file_path)


def test_load_color_mapping_from_file(tmp_path: Path) -> None:
    file_path = tmp_path / "map.json"
    file_path.write_text('{"#000000":"image","#ff0000":"text"}', encoding="utf-8")

    mapping = load_color_mapping(None, file_path)
    assert mapping["#000000"] == "image"
    assert mapping["#ff0000"] == "text"
