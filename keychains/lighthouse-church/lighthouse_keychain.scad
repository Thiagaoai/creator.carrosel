// =============================================================
// LIGHT HOUSE CHURCH — 3D printable keychain (two-color)
// Bambu Lab A1 / 0.4 mm nozzle / 0.20 mm layers
//
// Construction rules (same as the PLJ Carpentry tag):
//   * 3.2 mm rigid base (blue #0F4C9C), 100% flat back
//   * 1.6 mm raised relief (white #FFFFFF)
//   * relief penetrates 0.04 mm into the base (no z-fighting)
//   * ALL white geometry is ONE boolean union -> one watertight
//     mesh, no overlapping outlines behind the lettering
//   * minimum stroke >= 1 mm (printable with a 0.4 mm nozzle)
//
// Export:
//   openscad -D 'part="base"'   -o base_blue.stl    this_file.scad
//   openscad -D 'part="relief"' -o relief_white.stl this_file.scad
// =============================================================

part = "all"; // "all" (preview) | "base" | "relief"

/* [Tag] */
tag_d         = 50;    // tag diameter
base_h        = 3.2;   // base thickness
relief_h      = 1.6;   // relief height above the base
sink          = 0.04;  // relief penetration into the base

/* [Hanger loop] */
loop_outer_r  = 6;     // outer radius of the loop
loop_hole_d   = 6;     // keyring hole diameter
loop_center_y = 27;    // loop center, relative to tag center

/* [Outer ring] */
ring_outer_r  = 22;    // outer radius of the white ring
ring_w        = 2.2;   // ring stroke width
gap_pad       = 5;     // extra ring gap on each side of the text (deg)

/* [Curved label] */
label      = "LIGHT HOUSE CHURCH";
font_name  = "Anton:style=Regular";
font_size  = 4.4;      // cap height ~5.25 mm, 'I' stem ~1.01 mm
text_r     = 22.7;     // baseline radius (letter tops point inward)
tracking   = 0.08;     // extra letter spacing, em fraction
text_boost = 0.05;     // 2D offset safety margin on stroke width
// OpenSCAD renders text() glyphs at size/0.72 em (72/100 dpi quirk);
// the same factor must be applied to the advance-width math below.
ft_scale   = 1 / 0.72;

/* [Lighthouse icon] */
icon_dy      = 0.5;    // vertical offset of the whole icon
tower_top_y  = 8.2;    // tower top edge
tower_bot_y  = -10;    // tower bottom (before the wave cut)
tower_top_hw = 2.6;    // half width at the top
tower_bot_hw = 5.3;    // half width at the bottom
ray_cy       = 9.7;    // center of the ray fan
ray_in       = 3.0;    // ray fan inner radius
ray_out      = 7.8;    // ray fan outer radius
ray_w        = 2.0;    // ray stroke width

$fn = 160;

// ---------------- curved text helpers ----------------
// Exact Anton advance widths (em fraction, measured from the TTF
// hmtx table) for the arc layout.
function _cw(c) =
      c == "I" ? 0.227
    : c == "L" ? 0.397
    : c == "T" ? 0.396
    : c == "G" ? 0.485
    : c == "H" ? 0.499
    : c == "O" ? 0.486
    : c == "U" ? 0.474
    : c == "S" ? 0.461
    : c == "E" ? 0.412
    : c == "C" ? 0.474
    : c == "R" ? 0.477
    : c == " " ? 0.234
    : 0.480;

_widths = [for (i = [0:len(label) - 1]) _cw(label[i]) + tracking];

function _sum(v, i) = i <= 0 ? 0 : v[i - 1] + _sum(v, i - 1);

_arc_len   = (_sum(_widths, len(label)) - tracking) * font_size * ft_scale;
_theta_tot = _arc_len / text_r * 180 / PI;

// Angle of char i measured from the bottom center (+ = left side).
function _char_a(i) =
    _theta_tot / 2
    - (_sum(_widths, i) + (_widths[i] - tracking) / 2)
      * font_size * ft_scale / text_r * 180 / PI;

module label_2d() {
    offset(delta = text_boost)
        for (i = [0:len(label) - 1])
            rotate([0, 0, -_char_a(i)])
                translate([0, -text_r])
                    text(label[i], size = font_size, font = font_name,
                         halign = "center", valign = "baseline");
}

// ---------------- ring with a gap for the text ----------------
module ring_2d() {
    half_gap = _theta_tot / 2 + gap_pad;
    difference() {
        circle(r = ring_outer_r);
        circle(r = ring_outer_r - ring_w);
        // wedge over the bottom arc occupied by the label
        polygon(concat([[0, 0]],
            [for (a = [-half_gap:2:half_gap])
                [40 * sin(a), -40 * cos(a)]]));
    }
}

// ---------------- lighthouse icon ----------------
module tower_2d() {
    difference() {
        polygon([
            [-tower_top_hw, tower_top_y],
            [ tower_top_hw, tower_top_y],
            [ tower_bot_hw, tower_bot_y],
            [-tower_bot_hw, tower_bot_y]
        ]);
        // concave wave cut, deeper on the left, dipping to the right
        translate([-6, -31]) circle(r = 23.5);
    }
}

module rays_2d() {
    translate([0, ray_cy])
        for (ang = [0, 45, 90, 135, 180])
            rotate([0, 0, ang])
                translate([(ray_in + ray_out) / 2, 0])
                    square([ray_out - ray_in, ray_w], center = true);
}

module icon_2d() {
    translate([0, icon_dy]) {
        tower_2d();
        rays_2d();
    }
}

// ---------------- parts ----------------
module base_2d() {
    difference() {
        union() {
            circle(d = tag_d);
            translate([0, loop_center_y]) circle(r = loop_outer_r);
        }
        translate([0, loop_center_y]) circle(d = loop_hole_d);
    }
}

module base_3d() {
    linear_extrude(height = base_h)
        base_2d();
}

// ONE union of all white geometry, extruded once -> single mesh.
module relief_3d() {
    translate([0, 0, base_h - sink])
        linear_extrude(height = relief_h + sink)
            union() {
                ring_2d();
                icon_2d();
                label_2d();
            }
}

// ---------------- output ----------------
if (part == "base") {
    base_3d();
} else if (part == "relief") {
    relief_3d();
} else if (part == "icon") {
    icon_2d();
} else {
    color("#0F4C9C") base_3d();
    color("#FFFFFF") relief_3d();
}
