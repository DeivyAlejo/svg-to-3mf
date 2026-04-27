from __future__ import annotations

import json
from pathlib import Path

VALID_ROLES = {"image", "text"}


class ColorMappingError(ValueError):
    """Raised when color-role mapping input is invalid."""


def normalize_hex_color(raw: str) -> str:
    value = raw.strip().lower()
    if not value:
        raise ColorMappingError("Color value is empty")

    if not value.startswith("#"):
        raise ColorMappingError(f"Color must start with '#': {raw!r}")

    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])

    if len(value) != 7:
        raise ColorMappingError(f"Color must be #RGB or #RRGGBB: {raw!r}")

    hex_digits = value[1:]
    if any(ch not in "0123456789abcdef" for ch in hex_digits):
        raise ColorMappingError(f"Color has non-hex digits: {raw!r}")

    return value


def _parse_mapping_json(raw_json: str) -> dict[str, str]:
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ColorMappingError(f"Invalid JSON for color mapping: {exc}") from exc

    if not isinstance(payload, dict):
        raise ColorMappingError("Color mapping JSON must be an object")

    mapping: dict[str, str] = {}
    for raw_color, raw_role in payload.items():
        if not isinstance(raw_color, str):
            raise ColorMappingError("Color keys in mapping must be strings")
        if not isinstance(raw_role, str):
            raise ColorMappingError("Role values in mapping must be strings")

        color = normalize_hex_color(raw_color)
        role = raw_role.strip().lower()

        if role not in VALID_ROLES:
            raise ColorMappingError(
                f"Unsupported role {raw_role!r}. Allowed roles: {sorted(VALID_ROLES)}"
            )

        if color in mapping and mapping[color] != role:
            raise ColorMappingError(f"Color {color} is assigned to multiple roles")

        mapping[color] = role

    roles = set(mapping.values())
    if len(mapping) != 2:
        raise ColorMappingError("Color mapping must contain exactly 2 colors")

    if roles != VALID_ROLES:
        raise ColorMappingError(
            "Color mapping must contain exactly the roles 'image' and 'text'"
        )

    return mapping


def load_color_mapping(inline_json: str | None, json_file: Path | None) -> dict[str, str]:
    if bool(inline_json) == bool(json_file):
        raise ColorMappingError(
            "Provide exactly one of --color-map or --color-map-file"
        )

    if inline_json:
        return _parse_mapping_json(inline_json)

    assert json_file is not None

    if not json_file.exists():
        raise ColorMappingError(f"Color map file does not exist: {json_file}")

    try:
        raw = json_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ColorMappingError(f"Unable to read color map file {json_file}: {exc}") from exc

    return _parse_mapping_json(raw)
