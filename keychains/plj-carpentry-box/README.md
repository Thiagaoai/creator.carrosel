# PLJ Carpentry — presentation gift box (Bambu A1 / A1 mini / P1S)

Two-piece presentation box for the 50 mm PLJ Carpentry keychain.
Black PLA with the PLJ logo (saw blade, crossed tools, "PLJ
CARPENTRY" in Anton) as a flush yellow inlay on the lid.

## Files

| File | Purpose |
| --- | --- |
| `plj_gift_box.3mf` | Bambu Studio **project** — open and print. Base + lid on one plate, filament 1 = black, filament 2 = yellow, settings embedded. |
| `base_black.stl` | Box base (filament 1) |
| `lid_black.stl` | Lid body (filament 1), print orientation (top face down) |
| `lid_logo_yellow.stl` | Yellow logo inlay (filament 2), same orientation |
| `plj_gift_box.scad` | Parametric OpenSCAD source |
| `preview_lid.png` / `preview_base.png` / `preview_logo.png` | Design previews |
| `build_box_3mf.py` | Rebuilds the .3mf from the STLs |

## Design

- Outer size: **66.6 x 86.6 x ~14 mm closed** (lid telescopes over the base)
- Base: 62 x 82 x 11 mm, 2 mm walls, 4 mm floor
- Keychain seat: 2.2 mm recess shaped like the tag (0.5 mm clearance),
  with room for the metal ring above the loop and a finger notch below
  the tag to lift it out
- Lid: 2.4 mm face + 8 mm skirt, 0.25 mm fit clearance per side,
  finger notches on both short sides for easy opening
- Logo: 0.6 mm flush inlay (3 layers) on the OUTSIDE face of the lid;
  the lid prints top-face-down on the Textured PEI plate so the face
  gets the leather-look texture. The logo is mirrored in the mesh on
  purpose — it reads correctly from outside the box.
- Inlay penetrates 0.04 mm into the lid body (no z-fighting); the
  logo is one boolean union; minimum stroke >= 1 mm

## Printing

Open `plj_gift_box.3mf` in Bambu Studio (choose "Open as project"),
check AMS mapping (slot with BLACK PLA = filament 1, YELLOW = 2),
slice, print. Embedded: Textured PEI, 65 C bed, 0.20 mm layers,
3 walls, 15% gyroid, no supports, no brim, back seam, topmost
ironing 10% / 30 mm/s, 0.1 mm elephant-foot compensation, prime
tower on (the lid face swaps colors in the first 3 layers).

Printer notes:
- **A1 / P1S**: print as-is.
- **A1 mini**: after opening, switch the printer to "Bambu Lab A1
  mini 0.4 nozzle" and click auto-arrange (plate is smaller); both
  parts fit with room to spare.

## Regenerating

```bash
openscad --render -o base_black.stl      --export-format binstl -D 'part="base"'       plj_gift_box.scad
openscad --render -o lid_black.stl       --export-format binstl -D 'part="lid_black"'  plj_gift_box.scad
openscad --render -o lid_logo_yellow.stl --export-format binstl -D 'part="lid_yellow"' plj_gift_box.scad
python3 build_box_3mf.py
```

Requires the Anton font installed (Google Fonts).
