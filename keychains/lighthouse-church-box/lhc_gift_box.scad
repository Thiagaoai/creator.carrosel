// =============================================================
// LIGHT HOUSE CHURCH — presentation gift box for the 50 mm keychain
// Bambu Lab A1 / A1 mini / P1S, 0.4 mm nozzle, two-color
//
// Two pieces, both modeled READY TO PRINT (no supports):
//   * base  — printed floor-down; inner floor has a recessed seat
//             shaped like the keychain so it sits centered
//   * lid   — telescoping cap, printed TOP-FACE-DOWN on the
//             Textured PEI plate; the church logo is a flush
//             two-color inlay on the first layers (white logo in a
//             blue lid), so the outside gets the PEI leather look
//
// Same construction rules as the keychain:
//   * logo is ONE boolean union, no overlapping outlines
//   * yellow inlay penetrates 0.04 mm into the black lid body
//   * strokes >= 1 mm
//
// The logo is MIRRORED in the lid meshes because the lid prints
// face-down; it reads correctly from the outside of the box.
//
// part = "all" | "base" | "lid_black" | "lid_yellow" | "logo"
// =============================================================

part = "all";

/* [Keychain being boxed] */
key_tag_r    = 25;    // 50 mm tag
key_loop_r   = 6;
key_loop_cy  = 27;
seat_clear   = 0.5;   // pocket clearance around the keychain
seat_depth   = 2.2;

/* [Box] */
cavity_w     = 58;    // inner width  (x)
cavity_l     = 78;    // inner length (y)
cavity_dy    = 4;     // cavity shifted up to center the pocket
cavity_h     = 7;     // inner depth above the floor
floor_h      = 4;
wall         = 2;
corner_r     = 8;

/* [Lid] */
lid_top_h    = 2.4;   // lid face thickness (includes the inlay)
lid_wall     = 1.8;
lid_skirt    = 8;     // how far the lid wraps down over the base
fit_clear    = 0.25;  // per side, lid <-> base
notch_r      = 7;     // finger notches on the lid's open edge

/* [Logo inlay] */
inlay_h      = 0.6;   // 3 layers of 0.2
sink         = 0.04;

/* [Logo geometry] */
// The lid logo IS the keychain relief (ring + lighthouse + curved
// "LIGHT HOUSE CHURCH" in Anton), reused from the keychain source
// and scaled up to fit the lid.
logo_scale   = 1.2;

$fn = 120;

use <../lighthouse-church/lighthouse_keychain.scad>

// ------------------------------------------------------------
// helpers
// ------------------------------------------------------------
module rrect(w, l, r) {
    offset(r = r) square([w - 2 * r, l - 2 * r], center = true);
}

module logo_2d() { // ONE union, straight from the keychain design
    scale([logo_scale, logo_scale]) union() {
        ring_2d();
        icon_2d();
        label_2d();
    }
}

logo_dy = 0;

// ------------------------------------------------------------
// base (printed floor-down)
// ------------------------------------------------------------
module keychain_pocket_2d() {
    union() {
        offset(delta = seat_clear) {
            circle(r = key_tag_r);
            translate([0, key_loop_cy]) circle(r = key_loop_r);
        }
        translate([0, 33.5]) circle(r = 8);   // room for the metal ring
        translate([0, -key_tag_r]) circle(r = 8); // finger notch to lift
    }
}

base_w = cavity_w + 2 * wall;
base_l = cavity_l + 2 * wall;
base_h = floor_h + cavity_h;

module base_3d() {
    difference() {
        linear_extrude(height = base_h)
            rrect(base_w, base_l, corner_r);
        translate([0, cavity_dy, floor_h])
            linear_extrude(height = cavity_h + 0.01)
                rrect(cavity_w, cavity_l, corner_r - wall);
        translate([0, 0, floor_h - seat_depth])
            linear_extrude(height = seat_depth + 0.01)
                keychain_pocket_2d();
    }
}

// ------------------------------------------------------------
// lid (printed TOP-FACE-DOWN: z0 = outside of the lid)
// ------------------------------------------------------------
lid_in_w = base_w + 2 * fit_clear;
lid_in_l = base_l + 2 * fit_clear;
lid_w = lid_in_w + 2 * lid_wall;
lid_l = lid_in_l + 2 * lid_wall;
lid_h = lid_top_h + lid_skirt;

module lid_logo_2d() { // mirrored: reads correctly from outside
    mirror([1, 0]) translate([0, logo_dy]) logo_2d();
}

module lid_black_3d() {
    difference() {
        linear_extrude(height = lid_h)
            rrect(lid_w, lid_l, corner_r + lid_wall + fit_clear);
        // pocket that receives the base
        translate([0, 0, lid_top_h])
            linear_extrude(height = lid_skirt + 0.01)
                rrect(lid_in_w, lid_in_l, corner_r + fit_clear);
        // logo inlay pocket on the plate face
        translate([0, 0, -0.01])
            linear_extrude(height = inlay_h + 0.01)
                lid_logo_2d();
        // finger notches on the open edge (short sides)
        for (sx = [-1, 1])
            translate([sx * lid_w / 2, 0, lid_h])
                rotate([90, 0, 0])
                    cylinder(r = notch_r, h = lid_l + 10, center = true);
    }
}

module lid_yellow_3d() {
    linear_extrude(height = inlay_h + sink) // 0.04 into the black body
        lid_logo_2d();
}

// ------------------------------------------------------------
// output
// ------------------------------------------------------------
if (part == "base") {
    base_3d();
} else if (part == "lid_black") {
    lid_black_3d();
} else if (part == "lid_yellow") {
    lid_yellow_3d();
} else if (part == "logo") {
    logo_2d();
} else if (part == "layer1") {
    // what the slicer Preview shows on the lid's first layer (top view)
    color("#3A3A3A") linear_extrude(height = 0.2)
        projection(cut = true) translate([0, 0, -0.1]) lid_black_3d();
    color("#FFFFFF") translate([0, 0, 0.25]) linear_extrude(height = 0.2)
        projection(cut = true) translate([0, 0, -0.1]) lid_yellow_3d();
} else if (part == "lid_display") {
    // lid flipped to how it looks in use (logo facing up)
    rotate([0, 180, 0]) translate([0, 0, -lid_h]) {
        color("#0F4C9C") lid_black_3d();
        color("#FFFFFF") lid_yellow_3d();
    }
} else {
    color("#0F4C9C") translate([-(base_w / 2 + 8), 0, 0]) base_3d();
    translate([lid_w / 2 + 8, 0, 0]) {
        color("#0F4C9C") lid_black_3d();
        color("#FFFFFF") lid_yellow_3d();
    }
}
