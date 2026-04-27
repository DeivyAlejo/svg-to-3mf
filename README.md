# svg-to-3mf-text

CLI tool to convert a two-color SVG into a single multi-material 3MF object.

## Current status

Implemented now:

- CLI contract and defaults
- Color mapping JSON parsing and validation
- Input/output/config validation
- SVG raster-based two-color segmentation
- 3MF export with two base materials (`image`, `text`) in one object
- Bed-side orientation control via rotation (`face-up` / `face-down`)
- **2D corner fillet rounding** via morphological operations (default 0.4 mm, configurable)
- Unified solid geometry (text layers stacked on image base, no gaps)

Not implemented yet:

- True vector polygon extraction for all SVG primitives
- Advanced paint handling (gradients/patterns)
- Optional debug preview exports

## Usage

### Basic command

```bash
uv run svg-to-3mf input.svg --color-map '{"#000000":"image","#ff0000":"text"}'
```

### CLI Options

#### Required arguments

- **`input_svg`** — Path to the input two-color SVG file

#### Color mapping (required, one of)

- **`--color-map`** — Inline JSON mapping colors to roles (e.g., `{"#000000":"image","#ff0000":"text"}`)
- **`--color-map-file`** — Path to a JSON file containing the color-role mapping

The mapping must contain exactly two roles: `image` and `text`.

Example JSON file:
```json
{"#000000":"image","#ff0000":"text"}
```

#### Output options

- **`-o, --output`** — Output 3MF file path (default: `<input_stem>.3mf` in same directory as input)

#### Extrusion heights (defaults in mm)

- **`--image-height`** — Image/background extrusion height (default: `3.0` mm)
- **`--text-height`** — Text layer extrusion height (default: `0.6` mm)

#### Bed orientation

- **`--bed-side`** — Bed orientation control: `face-up` or `face-down` (default: `face-up`)
  - `face-up`: Model printed with current orientation
  - `face-down`: Model rotated 180° around Y-axis before export

#### Geometry refinement

- **`--rounding-radius`** — 2D corner rounding radius in mm (default: `0.4` mm)
  - Applies morphological smoothing to round corners on both image and text regions
- **`--min-region-area`** — Remove tiny polygon artifacts below this area in mm² (default: `0.01` mm²)

#### Advanced

- **`--auto-detect-colors`** — Enable fallback auto-detection (reserved; currently requires explicit mapping)

### Examples

**Basic conversion with defaults:**
```bash
uv run svg-to-3mf design.svg --color-map '{"#000000":"image","#ff0000":"text"}'
```

**Custom heights and output path:**
```bash
uv run svg-to-3mf design.svg \
  --color-map '{"#000000":"image","#ff0000":"text"}' \
  -o output.3mf \
  --image-height 2.5 \
  --text-height 0.8
```

**Face-down orientation:**
```bash
uv run svg-to-3mf design.svg \
  --color-map '{"#000000":"image","#ff0000":"text"}' \
  --bed-side face-down
```

**Using a color map file:**
```bash
uv run svg-to-3mf design.svg --color-map-file colors.json
```
