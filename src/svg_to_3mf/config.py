from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VALID_BED_SIDES = {"face-up", "face-down"}


@dataclass(frozen=True)
class ConversionConfig:
    input_svg: Path
    output_3mf: Path
    image_height_mm: float = 3.0
    text_height_mm: float = 0.6
    bed_side: str = "face-up"
    rounding_radius_mm: float = 0.4
    auto_detect_colors: bool = False
    min_region_area_mm2: float = 0.01

    def validate(self) -> None:
        if not self.input_svg.exists():
            raise ValueError(f"Input SVG does not exist: {self.input_svg}")

        if self.input_svg.suffix.lower() != ".svg":
            raise ValueError(f"Input must be an SVG file: {self.input_svg}")

        if self.output_3mf.suffix.lower() != ".3mf":
            raise ValueError(f"Output must end with .3mf: {self.output_3mf}")

        if self.image_height_mm <= 0:
            raise ValueError("--image-height must be > 0")

        if self.text_height_mm <= 0:
            raise ValueError("--text-height must be > 0")

        if self.rounding_radius_mm < 0:
            raise ValueError("--rounding-radius must be >= 0")

        if self.min_region_area_mm2 < 0:
            raise ValueError("--min-region-area must be >= 0")

        if self.bed_side not in VALID_BED_SIDES:
            raise ValueError(
                f"--bed-side must be one of {sorted(VALID_BED_SIDES)}; got {self.bed_side!r}"
            )
