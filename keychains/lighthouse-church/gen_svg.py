#!/usr/bin/env python3
"""Generate the Inkscape SVG version of the Light House Church keychain.

Same geometry as lighthouse_keychain.scad, drawn in real millimeters.
The label is live text on a circular path (font: Anton) so it stays
editable in Inkscape; select it and "Path > Object to Path" to outline.
"""
from __future__ import annotations

import math
from pathlib import Path

BLUE = "#0F4C9C"
WHITE = "#FFFFFF"

# --- parameters (keep in sync with the .scad) ---
TAG_R = 25.0
LOOP_R = 6.0
LOOP_HOLE_R = 3.0
LOOP_CY = 27.0          # model coords, y up, tag center at origin
RING_OUT = 22.0
RING_W = 2.2
GAP_PAD = 5.0           # deg
TEXT_R = 22.7
FONT_SIZE = 4.4 / 0.72  # OpenSCAD size 4.4 -> real em 6.11 mm
TRACKING_EM = 0.08
LABEL = "LIGHT HOUSE CHURCH"

ICON_DY = 0.5
TOWER_TOP_Y = 8.2
TOWER_BOT_Y = -10.0
TOWER_TOP_HW = 2.6
TOWER_BOT_HW = 5.3
WAVE_C = (-6.0, -31.0)  # wave-cut circle center (before ICON_DY)
WAVE_R = 23.5
RAY_CY = 9.7
RAY_IN = 3.0
RAY_OUT = 7.8
RAY_W = 2.0

# Anton advance widths (em) from the TTF hmtx table
CW = {
    "I": 0.227, "L": 0.397, "T": 0.396, "G": 0.485, "H": 0.499,
    "O": 0.486, "U": 0.474, "S": 0.461, "E": 0.412, "C": 0.474,
    "R": 0.477, " ": 0.234,
}

# document: 56 x 66 mm, tag center at (28, 37)
DOC_W, DOC_H = 56.0, 66.0
CX, CY = 28.0, 37.0


def P(x: float, y: float) -> str:
    """Model coords (y up, origin = tag center) -> svg 'x,y' string."""
    return f"{CX + x:.3f},{CY - y:.3f}"


def arc_theta() -> float:
    total_em = sum(CW[c] for c in LABEL) + TRACKING_EM * (len(LABEL) - 1)
    arc_len = total_em * FONT_SIZE
    return math.degrees(arc_len / TEXT_R)


def base_path() -> str:
    """Union outline of tag disc + hanger loop, hole as evenodd subpath."""
    # intersection of circle(TAG_R at origin) and circle(LOOP_R at 0,LOOP_CY)
    yi = (TAG_R**2 - LOOP_R**2 + LOOP_CY**2) / (2 * LOOP_CY)
    xi = math.sqrt(TAG_R**2 - yi**2)
    # disc: from (-xi, yi) the long way (through bottom) to (xi, yi)
    d = (
        f"M {P(-xi, yi)} "
        f"A {TAG_R} {TAG_R} 0 1 0 {P(xi, yi)} "
        # loop outer arc: from (xi, yi) over the top back to (-xi, yi)
        f"A {LOOP_R} {LOOP_R} 0 1 0 {P(-xi, yi)} Z "
        # keyring hole (subpath, evenodd punches it out) — full circle
        # drawn as two half arcs to avoid a degenerate single arc
        f"M {P(0, LOOP_CY + LOOP_HOLE_R)} "
        f"A {LOOP_HOLE_R} {LOOP_HOLE_R} 0 1 1 {P(0, LOOP_CY - LOOP_HOLE_R)} "
        f"A {LOOP_HOLE_R} {LOOP_HOLE_R} 0 1 1 {P(0, LOOP_CY + LOOP_HOLE_R)} Z"
    )
    return d


def ring_path() -> str:
    half_gap = arc_theta() / 2 + GAP_PAD
    # svg-parameter angle b: point = (cx + r cos b, cy + r sin b), b=90 bottom
    b1 = math.radians(90 + half_gap)   # lower-left ring end
    b2 = math.radians(90 - half_gap)   # lower-right ring end
    r_in = RING_OUT - RING_W

    def pt(r: float, b: float) -> str:
        return f"{CX + r * math.cos(b):.3f},{CY + r * math.sin(b):.3f}"

    return (
        f"M {pt(RING_OUT, b1)} "
        f"A {RING_OUT} {RING_OUT} 0 1 1 {pt(RING_OUT, b2)} "
        f"L {pt(r_in, b2)} "
        f"A {r_in} {r_in} 0 1 0 {pt(r_in, b1)} Z"
    )


def tower_path() -> str:
    cxw, cyw = WAVE_C[0], WAVE_C[1] + ICON_DY
    top = TOWER_TOP_Y + ICON_DY
    bot = TOWER_BOT_Y + ICON_DY

    def wave_y(x: float) -> float:
        return cyw + math.sqrt(WAVE_R**2 - (x - cxw) ** 2)

    left_y = max(wave_y(-TOWER_BOT_HW), bot)
    pts = [P(-TOWER_TOP_HW, top), P(TOWER_TOP_HW, top)]
    right_y = max(wave_y(TOWER_BOT_HW), bot)
    pts.append(P(TOWER_BOT_HW, right_y))
    # sample the concave wave cut from right to left
    n = 24
    for i in range(1, n):
        x = TOWER_BOT_HW - (2 * TOWER_BOT_HW) * i / n
        pts.append(P(x, max(wave_y(x), bot)))
    pts.append(P(-TOWER_BOT_HW, left_y))
    return "M " + " L ".join(pts) + " Z"


def ray_paths() -> list[str]:
    out = []
    for ang in (0, 45, 90, 135, 180):
        a = math.radians(ang)
        ux, uy = math.cos(a), math.sin(a)      # radial direction
        nx, ny = -uy, ux                        # normal
        cx_r = 0.0
        cy_r = RAY_CY + ICON_DY
        corners = []
        for r, s in ((RAY_IN, 1), (RAY_OUT, 1), (RAY_OUT, -1), (RAY_IN, -1)):
            x = cx_r + ux * r + nx * s * RAY_W / 2
            y = cy_r + uy * r + ny * s * RAY_W / 2
            corners.append(P(x, y))
        out.append("M " + " L ".join(corners) + " Z")
    return out


def text_arc_path() -> str:
    # baseline semicircle through the bottom, running left -> right
    return (
        f"M {CX - TEXT_R:.3f},{CY:.3f} "
        f"A {TEXT_R} {TEXT_R} 0 0 0 {CX + TEXT_R:.3f},{CY:.3f}"
    )


def build() -> None:
    rays = "\n    ".join(
        f'<path d="{d}" fill="{WHITE}"/>' for d in ray_paths()
    )
    letter_spacing = TRACKING_EM * FONT_SIZE
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{DOC_W}mm" height="{DOC_H}mm"
     viewBox="0 0 {DOC_W} {DOC_H}">
  <title>Light House Church keychain — 50 mm tag</title>
  <!-- All units are real millimeters. Font: Anton (Google Fonts).
       Text is live on a circular path; use Path > Object to Path in
       Inkscape to convert it to outlines. -->
  <defs>
    <path id="textarc" d="{text_arc_path()}"/>
  </defs>

  <g id="base-blue">
    <path d="{base_path()}" fill="{BLUE}" fill-rule="evenodd"/>
  </g>

  <g id="relief-white">
    <path id="ring" d="{ring_path()}" fill="{WHITE}"/>
    <path id="tower" d="{tower_path()}" fill="{WHITE}"/>
    {rays}
    <text font-family="Anton" font-size="{FONT_SIZE:.3f}"
          letter-spacing="{letter_spacing:.3f}" fill="{WHITE}"
          text-anchor="middle">
      <textPath xlink:href="#textarc" href="#textarc" startOffset="50%">{LABEL}</textPath>
    </text>
  </g>
</svg>
"""
    out = Path(__file__).parent / "lighthouse_keychain.svg"
    out.write_text(svg)
    print(f"wrote {out}")


if __name__ == "__main__":
    build()
