# Light House Church — 3D keychain (Bambu Lab A1)

50 mm circular two-color tag, same construction as the PLJ Carpentry
keychain: blue base (#0F4C9C) + white raised logo/lettering (#FFFFFF),
lighthouse beacon icon and "LIGHT HOUSE CHURCH" in Anton around the
bottom arc.

## Files

| File | Purpose |
| --- | --- |
| `lighthouse_keychain.3mf` | Bambu Studio **project** — open and print. Two parts of one object, filament 1 = blue base, filament 2 = white relief, print settings embedded. |
| `base_blue.stl` | Base only (filament 1) |
| `relief_white.stl` | Relief only (filament 2) |
| `lighthouse_keychain.scad` | Parametric OpenSCAD source (needs the Anton TTF installed) |
| `lighthouse_keychain.svg` | Vector version for Inkscape (live text on path, font Anton) |
| `preview_top.png` / `preview_3d.png` | Design previews |
| `build_3mf.py` | Rebuilds the .3mf from the two STLs |
| `gen_svg.py` | Regenerates the SVG |

## Dimensions / construction

- Tag Ø 50 mm, hanger loop on top with Ø 6 mm keyring hole
- Base 3.2 mm thick (rigid, warp-resistant), back 100% flat — print
  back-down on the Textured PEI plate
- Relief +1.6 mm, penetrating 0.04 mm into the base (no z-fighting)
- All white geometry is ONE boolean union — no overlapping outlines,
  so the slicer shows no stray lines behind the lettering
- Minimum stroke ~1.0 mm (Anton 'I' stem = 1.01 mm + 0.05 mm offset)
- Total height 4.8 mm

## Embedded print settings (A1, 0.4 mm nozzle)

- Plate: Textured PEI, bed 65 °C
- Layer 0.20 mm, 3 walls, infill 15% gyroid
- No supports, no brim, seam: back
- Ironing: Topmost surface, 10% flow, 30 mm/s
- Elephant-foot compensation 0.1 mm

## Regenerating

```bash
openscad --render -o base_blue.stl    --export-format binstl -D 'part="base"'   lighthouse_keychain.scad
openscad --render -o relief_white.stl --export-format binstl -D 'part="relief"' lighthouse_keychain.scad
python3 build_3mf.py
python3 gen_svg.py
```

The Anton font must be installed (e.g. `~/.fonts/Anton-Regular.ttf`,
from Google Fonts) before rendering the .scad.
