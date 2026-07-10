# Light House Church — presentation gift box (Bambu A1 / A1 mini / P1S)

Same SLIDING-LID box as the PLJ Carpentry one (`../plj-carpentry-box/`), with the
Light House Church logo instead: blue PLA body, white flush logo
inlay on the lid (ring + lighthouse beacon + "LIGHT HOUSE CHURCH" in
Anton — reused straight from the keychain source, scaled 1.2x).

## Files

| File | Purpose |
| --- | --- |
| `lhc_gift_box.3mf` | Bambu Studio **project** — open as project and print. Filament 1 = blue, filament 2 = white. |
| `box_base_blue.stl` | Box base (filament 1) |
| `box_lid_blue.stl` | Lid body (filament 1), prints top-face-down |
| `box_lid_logo_white.stl` | White logo inlay (filament 2) |
| `lhc_gift_box.scad` | Parametric source (uses `../lighthouse-church/lighthouse_keychain.scad` for the logo) |
| `build_box_3mf.py` | Rebuilds the .3mf |

Construction, dimensions, print settings and printer notes are
identical to the PLJ box — see `../plj-carpentry-box/README.md`.
The logo is mirrored in the mesh on purpose (the lid prints
face-down); the slicer's first-layer preview shows it mirrored and
the printed lid reads correctly from outside.
