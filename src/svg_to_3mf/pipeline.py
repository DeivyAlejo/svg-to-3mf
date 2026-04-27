from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

import cairosvg
from PIL import Image
from scipy import ndimage

from .config import ConversionConfig


PX_PER_INCH = 96.0
MM_PER_INCH = 25.4
UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "in": MM_PER_INCH,
    "px": MM_PER_INCH / PX_PER_INCH,
    "pt": MM_PER_INCH / 72.0,
    "pc": MM_PER_INCH / 6.0,
}
LENGTH_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$")


def _parse_svg_length_mm(raw_value: str) -> float:
    match = LENGTH_RE.match(raw_value)
    if not match:
        raise ValueError(f"Unsupported SVG length value: {raw_value!r}")

    value = float(match.group(1))
    unit = match.group(2).lower() or "px"

    if unit not in UNIT_TO_MM:
        raise ValueError(
            f"Unsupported SVG unit {unit!r}. Supported units: {sorted(UNIT_TO_MM)}"
        )

    return value * UNIT_TO_MM[unit]


def _svg_size_mm(svg_path: Path) -> tuple[float, float]:
    try:
        root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    except ET.ParseError as exc:
        raise ValueError(f"Invalid SVG XML: {exc}") from exc

    width_raw = root.attrib.get("width")
    height_raw = root.attrib.get("height")

    if width_raw and height_raw:
        return _parse_svg_length_mm(width_raw), _parse_svg_length_mm(height_raw)

    view_box = root.attrib.get("viewBox")
    if not view_box:
        raise ValueError(
            "SVG must include width/height or viewBox so physical size can be determined"
        )

    parts = view_box.replace(",", " ").split()
    if len(parts) != 4:
        raise ValueError(f"Invalid viewBox format: {view_box!r}")

    vb_width = float(parts[2])
    vb_height = float(parts[3])
    return vb_width * UNIT_TO_MM["px"], vb_height * UNIT_TO_MM["px"]


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _nearest_role(
    pixel: tuple[int, int, int],
    role_colors: dict[str, tuple[int, int, int]],
) -> str:
    best_role: str | None = None
    best_distance: int | None = None
    pr, pg, pb = pixel
    for role, (cr, cg, cb) in role_colors.items():
        distance = (pr - cr) * (pr - cr) + (pg - cg) * (pg - cg) + (pb - cb) * (pb - cb)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_role = role
    assert best_role is not None
    return best_role


def _rectangles_from_mask(mask: list[list[bool]]) -> list[tuple[int, int, int, int]]:
    if not mask:
        return []

    width = len(mask[0])
    active: dict[tuple[int, int], list[int]] = {}
    merged: list[tuple[int, int, int, int]] = []

    for y, row in enumerate(mask):
        runs: list[tuple[int, int]] = []
        x = 0
        while x < width:
            if not row[x]:
                x += 1
                continue
            start = x
            x += 1
            while x < width and row[x]:
                x += 1
            runs.append((start, x))

        new_active: dict[tuple[int, int], list[int]] = {}
        for run in runs:
            if run in active:
                rect = active[run]
                rect[3] = y + 1
                new_active[run] = rect
            else:
                new_active[run] = [run[0], run[1], y, y + 1]

        for run, rect in active.items():
            if run not in new_active:
                merged.append((rect[0], rect[1], rect[2], rect[3]))

        active = new_active

    for rect in active.values():
        merged.append((rect[0], rect[1], rect[2], rect[3]))

    return merged


def _add_box(
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int, int]],
    x: float,
    y: float,
    z: float,
    w: float,
    d: float,
    h: float,
    material_index: int,
) -> None:
    base = len(vertices)
    vertices.extend(
        [
            (x, y, z),
            (x + w, y, z),
            (x + w, y + d, z),
            (x, y + d, z),
            (x, y, z + h),
            (x + w, y, z + h),
            (x + w, y + d, z + h),
            (x, y + d, z + h),
        ]
    )

    faces = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]

    for a, b, c in faces:
        triangles.append((base + a, base + b, base + c, material_index))


def _apply_face_down_rotation(
    vertices: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    if not vertices:
        return vertices

    max_y = max(y for _, y, _ in vertices)
    max_z = max(z for _, _, z in vertices)
    return [(x, max_y - y, max_z - z) for x, y, z in vertices]


def _write_3mf(
    output_3mf: Path,
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int, int]],
) -> None:
    verts_xml = "\n".join(
        f'          <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>'
        for x, y, z in vertices
    )
    tris_xml = "\n".join(
        f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" pid="1" p1="{mat}"/>'
        for v1, v2, v3, mat in triangles
    )

    model_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <basematerials id="1">
      <base name="image" displaycolor="#000000"/>
      <base name="text" displaycolor="#FF0000"/>
    </basematerials>
    <object id="2" type="model">
      <mesh>
        <vertices>
{verts_xml}
        </vertices>
        <triangles>
{tris_xml}
        </triangles>
      </mesh>
    </object>
  </resources>
  <build>
    <item objectid="2"/>
  </build>
</model>
'''

    content_types = '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
'''

    rels = '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
'''

    output_3mf.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_3mf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml)




def _apply_mask_rounding(
    mask: list[list[bool]], radius_pixels: float
) -> list[list[bool]]:
    """
    Apply 2D corner rounding to a boolean mask using morphological operations.
    
    Uses erosion (shrink) followed by dilation (expand) to create smooth, rounded corners.
    
    Args:
        mask: Boolean 2D mask (True = active pixel)
        radius_pixels: Rounding radius in pixels
    
    Returns:
        Rounded boolean mask
    """
    if radius_pixels <= 0 or not mask or not mask[0]:
        return mask
    
    import numpy as np
    
    # Convert mask to numpy array
    arr = np.array(mask, dtype=np.uint8)
    
    # Create a circular structuring element for smooth rounding
    radius_int = max(1, int(round(radius_pixels)))
    struct = ndimage.generate_binary_structure(2, 2)
    
    # Apply morphological closing (dilation then erosion) for gentle rounding
    # This preserves size better than erode-dilate sequence
    rounded = ndimage.binary_closing(arr, structure=struct, iterations=radius_int)
    
    # Convert back to boolean list of lists
    return [[bool(v) for v in row] for row in rounded]


def run_conversion(config: ConversionConfig, color_mapping: dict[str, str]) -> None:
    """Execute SVG->3MF conversion using two-color raster classification."""
    config.validate()

    if set(color_mapping.values()) != {"image", "text"}:
        raise ValueError("Color mapping must include image/text roles")

    width_mm, height_mm = _svg_size_mm(config.input_svg)
    if width_mm <= 0 or height_mm <= 0:
        raise ValueError("SVG width/height must be > 0")

    pixels_per_mm = 8.0
    width_px = max(32, int(round(width_mm * pixels_per_mm)))
    height_px = max(32, int(round(height_mm * pixels_per_mm)))

    png_bytes = cairosvg.svg2png(
        url=str(config.input_svg),
        output_width=width_px,
        output_height=height_px,
    )
    img = Image.open(BytesIO(png_bytes)).convert("RGBA")

    role_to_color: dict[str, tuple[int, int, int]] = {}
    for color, role in color_mapping.items():
        role_to_color[role] = _hex_to_rgb(color)

    masks: dict[str, list[list[bool]]] = {
        "image": [[False] * width_px for _ in range(height_px)],
        "text": [[False] * width_px for _ in range(height_px)],
    }

    pixel_access = img.load()
    for y in range(height_px):
        for x in range(width_px):
            r, g, b, a = pixel_access[x, y]
            if a == 0:
                continue
            role = _nearest_role((r, g, b), role_to_color)
            masks[role][y][x] = True

    pixel_area_mm2 = (width_mm / width_px) * (height_mm / height_px)
    image_height_mm = config.image_height_mm
    text_height_mm = config.text_height_mm

    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int, int]] = []
    role_counts = {"image": 0, "text": 0}

    scale_x = width_mm / width_px
    scale_y = height_mm / height_px

    rounding_radius_pixels = (
        config.rounding_radius_mm / scale_x + config.rounding_radius_mm / scale_y
    ) / 2.0
    rounded_image_mask = _apply_mask_rounding(masks["image"], rounding_radius_pixels)
    rounded_text_mask = _apply_mask_rounding(masks["text"], rounding_radius_pixels)

    # Give text precedence where rounded masks touch so volumes remain disjoint.
    for y in range(height_px):
        for x in range(width_px):
            if rounded_text_mask[y][x]:
                rounded_image_mask[y][x] = False

    if text_height_mm < image_height_mm:
        # Lower layer supports both regions with image material to keep the model unified.
        lower_height_mm = image_height_mm - text_height_mm
        combined_mask = [
            [
                rounded_image_mask[y][x] or rounded_text_mask[y][x]
                for x in range(width_px)
            ]
            for y in range(height_px)
        ]

        support_rectangles = _rectangles_from_mask(combined_mask)
        for x0, x1, y0, y1 in support_rectangles:
            area_mm2 = (x1 - x0) * (y1 - y0) * pixel_area_mm2
            if area_mm2 < config.min_region_area_mm2:
                continue

            role_counts["image"] += 1
            _add_box(
                vertices=vertices,
                triangles=triangles,
                x=x0 * scale_x,
                y=y0 * scale_y,
                z=0.0,
                w=(x1 - x0) * scale_x,
                d=(y1 - y0) * scale_y,
                h=lower_height_mm,
                material_index=0,
            )

        # Upper layer is split by role so image/text occupy different triangles.
        upper_z = lower_height_mm

        image_rectangles = _rectangles_from_mask(rounded_image_mask)
        for x0, x1, y0, y1 in image_rectangles:
            area_mm2 = (x1 - x0) * (y1 - y0) * pixel_area_mm2
            if area_mm2 < config.min_region_area_mm2:
                continue

            role_counts["image"] += 1
            _add_box(
                vertices=vertices,
                triangles=triangles,
                x=x0 * scale_x,
                y=y0 * scale_y,
                z=upper_z,
                w=(x1 - x0) * scale_x,
                d=(y1 - y0) * scale_y,
                h=text_height_mm,
                material_index=0,
            )

        text_rectangles = _rectangles_from_mask(rounded_text_mask)
        for x0, x1, y0, y1 in text_rectangles:
            area_mm2 = (x1 - x0) * (y1 - y0) * pixel_area_mm2
            if area_mm2 < config.min_region_area_mm2:
                continue

            role_counts["text"] += 1
            _add_box(
                vertices=vertices,
                triangles=triangles,
                x=x0 * scale_x,
                y=y0 * scale_y,
                z=upper_z,
                w=(x1 - x0) * scale_x,
                d=(y1 - y0) * scale_y,
                h=text_height_mm,
                material_index=1,
            )
    else:
        image_rectangles = _rectangles_from_mask(rounded_image_mask)
        for x0, x1, y0, y1 in image_rectangles:
            area_mm2 = (x1 - x0) * (y1 - y0) * pixel_area_mm2
            if area_mm2 < config.min_region_area_mm2:
                continue

            role_counts["image"] += 1
            _add_box(
                vertices=vertices,
                triangles=triangles,
                x=x0 * scale_x,
                y=y0 * scale_y,
                z=0.0,
                w=(x1 - x0) * scale_x,
                d=(y1 - y0) * scale_y,
                h=image_height_mm,
                material_index=0,
            )

        text_rectangles = _rectangles_from_mask(rounded_text_mask)
        for x0, x1, y0, y1 in text_rectangles:
            area_mm2 = (x1 - x0) * (y1 - y0) * pixel_area_mm2
            if area_mm2 < config.min_region_area_mm2:
                continue

            role_counts["text"] += 1
            _add_box(
                vertices=vertices,
                triangles=triangles,
                x=x0 * scale_x,
                y=y0 * scale_y,
                z=0.0,
                w=(x1 - x0) * scale_x,
                d=(y1 - y0) * scale_y,
                h=text_height_mm,
                material_index=1,
            )

    if role_counts["image"] == 0 or role_counts["text"] == 0:
        raise ValueError(
            "Converted SVG did not produce non-empty regions for both roles. "
            "Check color mapping and SVG colors."
        )

    if config.bed_side == "face-down":
        vertices = _apply_face_down_rotation(vertices)

    _write_3mf(config.output_3mf, vertices, triangles)
