from __future__ import annotations

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "basic_rect_text.3mf"


def add_box(vertices, triangles, x, y, z, w, d, h, material_index):
    base = len(vertices)
    # 8 vertices for a cuboid
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

    # 12 triangles (2 per face)
    faces = [
        (0, 2, 1), (0, 3, 2),  # bottom
        (4, 5, 6), (4, 6, 7),  # top
        (0, 1, 5), (0, 5, 4),  # front
        (1, 2, 6), (1, 6, 5),  # right
        (2, 3, 7), (2, 7, 6),  # back
        (3, 0, 4), (3, 4, 7),  # left
    ]
    for a, b, c in faces:
        triangles.append((base + a, base + b, base + c, material_index))


def model_xml() -> str:
    vertices = []
    triangles = []

    # Main rectangle body (black) 100x60x2 mm
    add_box(vertices, triangles, x=0.0, y=0.0, z=0.0, w=100.0, d=60.0, h=2.0, material_index=0)

    # Raised "text area" placeholder (red) centered on top 40x12x0.8 mm
    add_box(vertices, triangles, x=30.0, y=24.0, z=2.0, w=40.0, d=12.0, h=0.8, material_index=1)

    verts_xml = "\n".join(
        f'          <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in vertices
    )
    tris_xml = "\n".join(
        f'          <triangle v1="{v1}" v2="{v2}" v3="{v3}" pid="1" p1="{m}"/>'
        for v1, v2, v3, m in triangles
    )

    return f'''<?xml version="1.0" encoding="UTF-8"?>
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


def main() -> None:
    out = OUT
    out.parent.mkdir(parents=True, exist_ok=True)

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

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("3D/3dmodel.model", model_xml())

    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
