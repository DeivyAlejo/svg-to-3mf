from pathlib import Path
import zipfile

from svg_to_3mf.cli import main


def test_cli_requires_existing_input(tmp_path: Path) -> None:
    rc = main(
        [
            str(tmp_path / "missing.svg"),
            "--color-map",
            '{"#000000":"image","#ff0000":"text"}',
        ]
    )
    assert rc == 2


def test_cli_generates_3mf_for_simple_svg(tmp_path: Path) -> None:
    svg = tmp_path / "input.svg"
    out = tmp_path / "output.3mf"
    svg.write_text(
        """
<svg xmlns='http://www.w3.org/2000/svg' width='40mm' height='20mm' viewBox='0 0 40 20'>
  <rect x='1' y='1' width='38' height='18' fill='#000000'/>
  <text x='20' y='12' text-anchor='middle' font-size='6' fill='#ff0000'>TEST</text>
</svg>
""".strip(),
        encoding="utf-8",
    )

    rc = main(
        [
            str(svg),
            "-o",
            str(out),
            "--color-map",
            '{"#000000":"image","#ff0000":"text"}',
        ]
    )
    assert rc == 0
    assert out.exists()

    with zipfile.ZipFile(out, "r") as zf:
        assert "3D/3dmodel.model" in zf.namelist()
        model_xml = zf.read("3D/3dmodel.model").decode("utf-8")
        assert "<object id=\"1\" name=\"image\" type=\"model\">" in model_xml
        assert "<object id=\"2\" name=\"text\" type=\"model\">" in model_xml
        assert "<item objectid=\"1\"/>" in model_xml
        assert "<item objectid=\"2\"/>" in model_xml
        assert "<triangle" in model_xml
