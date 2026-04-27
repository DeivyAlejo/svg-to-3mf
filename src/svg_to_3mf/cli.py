from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .color_mapping import ColorMappingError, load_color_mapping
from .config import ConversionConfig
from .pipeline import run_conversion


EXIT_OK = 0
EXIT_USAGE = 2
EXIT_RUNTIME = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="svg-to-3mf",
        description=(
            "Convert a two-color SVG into a one-piece multi-material 3MF for Bambu Studio."
        ),
    )

    parser.add_argument("input_svg", type=Path, help="Input two-color SVG file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output 3MF path (default: <input_stem>.3mf)",
    )

    parser.add_argument(
        "--image-height",
        type=float,
        default=3.0,
        help="Image/background extrusion height in mm (default: 3.0)",
    )
    parser.add_argument(
        "--text-height",
        type=float,
        default=0.6,
        help="Text extrusion height in mm (default: 0.6)",
    )
    parser.add_argument(
        "--bed-side",
        choices=["face-up", "face-down"],
        default="face-up",
        help="Bed orientation control using rotation only (default: face-up)",
    )
    parser.add_argument(
        "--rounding-radius",
        type=float,
        default=0.4,
        help="2D corner rounding radius in mm (default: 0.4)",
    )
    parser.add_argument(
        "--min-region-area",
        type=float,
        default=0.01,
        help="Remove tiny polygon artifacts below this area in mm^2 (default: 0.01)",
    )

    parser.add_argument(
        "--color-map",
        type=str,
        default=None,
        help='Inline JSON map, e.g. {"#000000":"image","#ff0000":"text"}',
    )
    parser.add_argument(
        "--color-map-file",
        type=Path,
        default=None,
        help="Path to JSON file containing color-role map",
    )
    parser.add_argument(
        "--auto-detect-colors",
        action="store_true",
        help="Enable fallback auto-detection (reserved; currently requires explicit mapping)",
    )

    return parser


def _resolve_output_path(input_svg: Path, output: Path | None) -> Path:
    if output is not None:
        return output
    return input_svg.with_suffix(".3mf")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_path = _resolve_output_path(args.input_svg, args.output)

    config = ConversionConfig(
        input_svg=args.input_svg,
        output_3mf=output_path,
        image_height_mm=args.image_height,
        text_height_mm=args.text_height,
        bed_side=args.bed_side,
        rounding_radius_mm=args.rounding_radius,
        auto_detect_colors=args.auto_detect_colors,
        min_region_area_mm2=args.min_region_area,
    )

    try:
        color_mapping = load_color_mapping(args.color_map, args.color_map_file)
        run_conversion(config, color_mapping)
    except (ColorMappingError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except NotImplementedError as exc:
        print(f"Not implemented: {exc}", file=sys.stderr)
        return EXIT_RUNTIME

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
