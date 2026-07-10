// =============================================================
// LIGHT HOUSE CHURCH — presentation gift box for the 50 mm keychain
// Bambu Lab A1 / A1 mini / P1S, 0.4 mm nozzle, two-color
//
// SLIDING-LID version: the lid runs inside side grooves (a real
// slot), clicks closed on a detent bump, and slides open through
// the front. A thumb scoop in the back rim gives a push surface;
// grip grooves on the lid face give traction. The keychain sits
// in a recessed seat, so it stays centered and protected.
//
// Two pieces, both modeled READY TO PRINT (no supports):
//   * base — printed floor-down; groove ceilings are 1.7 mm
//            micro-bridges (print fine without support)
//   * lid  — printed TOP-FACE-DOWN on the Textured PEI plate;
//            the church logo is a flush two-color inlay on the
//            first layers, so the face gets the leather-look texture
//
// Same construction rules as the keychain:
//   * logo is ONE boolean union, no overlapping outlines
//   * white inlay penetrates 0.04 mm into the blue lid body
//   * strokes >= 1 mm
//
// The logo is MIRRORED in the lid meshes because the lid prints
// face-down; it reads correctly from the outside of the box.
//
// part = "all" | "base" | "lid_black" | "lid_yellow" | "logo"
//        | "lid_display" | "layer1" | "assembly"
// =============================================================

part = "all";

/* [Keychain being boxed] */
key_tag_r    = 25;    // 50 mm tag
key_loop_r   = 6;
key_loop_cy  = 27;
seat_clear   = 0.5;   // pocket clearance around the keychain
seat_depth   = 2.2;
pocket_dy    = -3;    // pocket shifted to clear the back wall

/* [Box] */
base_w         = 62;
base_l         = 82;
endwall        = 2.4;  // front / back wall thickness
floor_h        = 4;
cavity_h       = 7;    // interior depth above the floor
corner_r_back  = 8;
corner_r_front = 2.5;  // small: the lid slot needs a wide flat front

/* [Sliding lid] */
lid_t          = 3.0;
slot_w         = 56;   // width of the front opening / groove span
groove_d       = 1.7;  // groove depth into each side wall
rim_t          = 1.2;  // rim thickness above the groove
lid_clear_side = 0.3;
lid_clear_top  = 0.3;
lid_clear_len  = 0.6;
scoop_r        = 8;    // thumb scoop in the back rim

/* [Detent] */
bump_h         = 0.7;  // rounded bump on the front wall top
front_drop     = 0.2;  // front wall sits this far below the lid

/* [Logo inlay] */
inlay_h      = 0.6;   // 3 layers of 0.2
sink         = 0.04;

/* [Logo geometry] */
// The lid logo IS the keychain relief (ring + lighthouse + curved
// "LIGHT HOUSE CHURCH" in Anton), reused from the keychain source
// and scaled to fit the sliding lid.
logo_scale   = 1.08;

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
// derived box dimensions
// ------------------------------------------------------------
inner_w   = slot_w - 2 * groove_d;              // interior width
inner_l   = base_l - 2 * endwall;               // interior length
ledge_z   = floor_h + cavity_h;                 // groove floor
groove_h  = lid_t + lid_clear_top;
base_top  = ledge_z + groove_h + rim_t;         // total base height
lid_w     = slot_w - 2 * lid_clear_side;
lid_l     = base_l - endwall - lid_clear_len;
closed_dy = -lid_clear_len - 0.3;               // lid offset when closed
bump_y    = -base_l / 2 + 1.2;                  // detent bump position

// footprint: big radii at the back, small at the front so the
// slot spans a flat front face
module box_outline() {
    hull() {
        for (sx = [-1, 1]) {
            translate([sx * (base_w / 2 - corner_r_back),
                       base_l / 2 - corner_r_back])
                circle(r = corner_r_back);
            translate([sx * (base_w / 2 - corner_r_front),
                       -base_l / 2 + corner_r_front])
                circle(r = corner_r_front);
        }
    }
}

// ------------------------------------------------------------
// base (printed floor-down)
// ------------------------------------------------------------
module keychain_pocket_2d() {
    translate([0, pocket_dy]) union() {
        offset(delta = seat_clear) {
            circle(r = key_tag_r);
            translate([0, key_loop_cy]) circle(r = key_loop_r);
        }
        translate([0, 33.5]) circle(r = 8);   // room for the metal ring
        translate([0, -key_tag_r]) circle(r = 8); // finger notch to lift
    }
}

module base_3d() {
    difference() {
        union() {
            linear_extrude(height = base_top) box_outline();
            // detent bump on the front wall top
            translate([0, bump_y, ledge_z - front_drop])
                scale([6, 1.5, bump_h]) sphere(r = 1);
        }
        // interior (open top between the rims)
        translate([0, 0, floor_h])
            linear_extrude(height = base_top)
                rrect(inner_w, inner_l, 5);
        // lid slot: grooves in both side walls + open front
        translate([-slot_w / 2, -base_l / 2 - 5, ledge_z])
            cube([slot_w, 5 + base_l - endwall, groove_h]);
        // front wall drop + open the front rim above the slot
        translate([-slot_w / 2, -base_l / 2 - 5, ledge_z - front_drop])
            cube([slot_w, 5 + endwall + 0.1, base_top]);
        // thumb scoop in the back rim (push the lid forward here)
        translate([0, base_l / 2, ledge_z + 1])
            cylinder(h = base_top, r = scoop_r);
        // keychain seat in the floor
        translate([0, 0, floor_h - seat_depth])
            linear_extrude(height = seat_depth + 0.01)
                keychain_pocket_2d();
    }
}

// ------------------------------------------------------------
// lid (printed TOP-FACE-DOWN: z0 = outside face of the lid)
// ------------------------------------------------------------
module lid_logo_2d() { // mirrored: reads correctly from outside
    mirror([1, 0]) translate([0, logo_dy]) logo_2d();
}

module lid_black_3d() {
    difference() {
        linear_extrude(height = lid_t) rrect(lid_w, lid_l, 2.5);
        // logo inlay pocket on the plate face
        translate([0, 0, -0.01])
            linear_extrude(height = inlay_h + 0.01)
                lid_logo_2d();
        // grip grooves on the face, near the front edge
        for (gy = [-36, -33, -30])
            translate([0, gy, -0.01])
                linear_extrude(height = 0.45)
                    square([26, 1.5], center = true);
        // detent recess on the underside, near the front edge
        translate([0, bump_y - closed_dy, lid_t])
            scale([7, 2.6, 1.1]) sphere(r = 1);
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
    rotate([0, 180, 0]) translate([0, 0, -lid_t]) {
        color("#0F4C9C") lid_black_3d();
        color("#FFFFFF") lid_yellow_3d();
    }
} else if (part == "assembly") {
    // box with the lid slid half open
    color("#0F4C9C") base_3d();
    translate([0, closed_dy - 30, ledge_z + lid_t])
        rotate([0, 180, 0]) {
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
