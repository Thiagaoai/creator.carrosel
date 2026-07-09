// PLJ CARPENTRY keychain — two-color print for Bambu Lab
// part = "base"   -> black body (disc + hanger loop), flat back
// part = "logo"   -> yellow raised artwork (saw blade, tools, bar, text)
// part = "all"    -> assembled preview
// part = "logo2d" -> flat 2D artwork (SVG export for Inkscape)
// part = "base2d" -> flat 2D outline (SVG export for Inkscape)

part = "all";

$fn = 128;

// ---- global dimensions (mm) ----
disc_r        = 25;    // 50 mm tag
base_h        = 2.4;   // black body thickness (12 layers @ 0.2)
relief_h      = 1.2;   // raised logo height (6 layers @ 0.2)
embed         = 0.04;  // logo sinks into base to fuse parts (kills z-fighting)

loop_c        = [0, disc_r + 1.5];
loop_outer_r  = 7.2;
loop_hole_r   = 3.0;   // fits a standard split ring

// ---- artwork layout ----
bar_top       = -4.4;
bar_h         = 2.2;
bar_half_len  = 21.5;

blade_c       = [0, bar_top];
blade_body_r  = 16.5;
blade_teeth_r = 19.0;
teeth_n       = 24;

arch_r        = 8.0;   // black arch under the blade

text_string   = "PLJ CARPENTRY";
text_font     = "Anton:style=Regular";
text_width    = 40;    // final width after auto-fit
text_top      = -8.2;  // top edge of the caps

// =====================================================
// 2D modules
// =====================================================

module blade_2d() {
    difference() {
        intersection() {
            union() {
                translate(blade_c) circle(r = blade_body_r);
                // hooked teeth
                for (i = [0 : teeth_n - 1])
                    translate(blade_c)
                        rotate(i * 360 / teeth_n)
                            translate([blade_body_r - 1.2, 0])
                                polygon([[0, -2.4], [0, 2.4],
                                         [blade_teeth_r - blade_body_r + 1.2, 0.4]]);
            }
            // only the part above the ground bar (slight overlap to fuse)
            translate([-40, bar_top - 1.2]) square([80, 60]);
        }
        // black arch that houses the tools
        translate(blade_c) circle(r = arch_r);
        // wood-grain swoosh (crescent cut)
        swoosh_2d();
    }
}

module swoosh_2d() {
    // thin wood-grain arc, kept clear of the arch below and the rim above
    difference() {
        translate([0, -1.0]) circle(r = 9.5);
        translate([0, -3.5]) circle(r = 10.0);
    }
}

module bar_2d() {
    translate([-bar_half_len, bar_top - bar_h])
        square([2 * bar_half_len, bar_h]);
}

module hammer_2d() {
    rotate(45) union() {
        translate([-0.8, -4.2]) square([1.6, 7.4]);   // handle
        translate([-2.7, 2.6])  square([5.4, 1.9]);   // head
        translate([0, 3.55])    circle(r = 0.95);     // rounded top
    }
}

module wrench_2d() {
    rotate(-45) union() {
        translate([-0.75, -4.2]) square([1.5, 7.6]);
        // open-end head with notch
        difference() {
            translate([0, 3.6]) circle(r = 2.1);
            translate([0, 3.6]) rotate(20)
                translate([-0.75, 0.4]) square([1.5, 3]);
        }
        translate([0, -4.2]) circle(r = 1.15);        // box end
    }
}

module tools_2d() {
    // scaled to float inside the arch without touching its edge
    translate([0, -1.0]) scale(0.82) {
        hammer_2d();
        wrench_2d();
    }
}

module name_2d() {
    // auto-fit the name to an exact width, then hang it below the bar
    translate([0, text_top])
        resize([text_width, 0], auto = true)
            text(text_string, size = 10, font = text_font,
                 halign = "center", valign = "top");
}

module logo_2d() {
    // everything is ONE union: no internal overlapping outlines,
    // so the slicer never sees stray lines behind the name
    union() {
        blade_2d();
        bar_2d();
        tools_2d();
        name_2d();
    }
}

module base_2d() {
    union() {
        circle(r = disc_r);
        translate(loop_c) circle(r = loop_outer_r);
        // smooth neck between loop and disc
        hull() {
            translate([0, disc_r - 4]) square([10, 1], center = true);
            translate(loop_c) circle(r = loop_outer_r - 1);
        }
    }
}

module base_hole_2d() {
    translate(loop_c) circle(r = loop_hole_r);
}

// =====================================================
// 3D parts
// =====================================================

module base_3d() {
    linear_extrude(height = base_h)
        difference() {
            base_2d();
            base_hole_2d();
        }
}

module logo_3d() {
    // starts slightly inside the base so both solids fuse in the slicer
    translate([0, 0, base_h - embed])
        linear_extrude(height = relief_h + embed)
            intersection() {
                logo_2d();
                offset(r = -1.2) base_2d();  // keep a clean black rim
            }
}

if (part == "base")   base_3d();
if (part == "logo")   logo_3d();
if (part == "all") {
    color("black")  base_3d();
    color("gold")   logo_3d();
}
if (part == "logo2d") logo_2d();
if (part == "base2d") difference() { base_2d(); base_hole_2d(); }
