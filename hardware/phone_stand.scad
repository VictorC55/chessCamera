// Clamp-on phone stand for recording the chess board from above.
//
// Simplified from the MakerWorld "modular extendable phone stand" (model 753423): keeps the desk clamp
// and a small amount of height adjustment, drops the spring-loaded phone grip and the modular arm.
// Four printed parts + one printed knob + one printed pin, and two bolts:
//
//   clamp   C-clamp for the table edge with the outer square tube built in (prints on its side)
//   post    inner square rod that slides in the tube, pin holes every 20 mm, hinge ears on top
//   tray    open frame the phone lies on, with lips on three sides and a hinge tab (prints flat)
//   knob    thumb knob that presses onto the clamp bolt's hex head
//   pin     height-setting pin through the tube and rod
//
// Hardware: 1x M6 x 70 hex bolt + M6 nut (clamp), 1x M4 x 35 bolt + M4 wing nut (tilt).
// Or set all_printed = true for a version with no metal parts (printed screw, tilt bolt and wing nut).
//
// How it holds the phone: the tray is an open frame, two rails and three bars, that stops short of the
// camera bump. The phone lies on it screen up, back on the bars, and its top (camera end) overhangs the
// frame so nothing sits under the lens. Tilted, gravity presses the phone into the frame; the bottom lip
// stops it sliding and a small hook on that lip stops it lifting, so a long phone is safe on a short frame.
// Tilt runs from vertical (camera looking across the table) to flat (camera looking straight down); lock
// any angle with the wing nut. Set phone_w and phone_t for your phone; tray_l is sized to clear most cameras.
//
// Height: hinge axis sits 248-348 mm above the table in 20 mm steps (pin holes). The 4th hole gives
// 308 mm, about a foot, with 88 mm of rod still inside the tube.
//
// Export one part:  openscad -D 'part="clamp"' -o clamp.stl phone_stand.scad   (same for post, tray, knob, pin)
// Preview the whole thing: part = "assembly".

part = "assembly";   // "assembly" | "clamp" | "post" | "tray" | "knob" | "pin" | "plate" (all parts laid out)
                     // all_printed = true adds "screw", "tilt_bolt", "wing_nut" and drops "knob"

// all_printed = false: clamp uses an M6 bolt + nut (knob presses onto the bolt head), tilt uses an M4 bolt + wing nut.
// all_printed = true:  no metal at all. The clamp screw and the tilt bolt are printed with a coarse round
//                      thread (a twisted off-centre circle, which prints cleanly and threads into a hole cut
//                      with the same shape plus clearance), and the tilt nut is a printed wing nut.
all_printed = true;
thr_pitch_c = 4;     // clamp screw: 12 mm thread, 4 mm pitch
thr_d_c     = 12;
thr_pitch_t = 2.5;   // tilt bolt: 8 mm thread, 2.5 mm pitch
thr_d_t     = 8;
thr_clear   = 0.8;   // diameter clearance between a printed thread and its printed hole (0.4 mm per side)
boss_h      = 6;     // extra thread depth under the lower jaw (all_printed only): 10 + 6 mm = 4 turns engaged

// ---------- phone ----------
phone_w  = 80;       // phone width incl. case, mm (measure yours; 2 mm clearance is added)
phone_t  = 10;       // phone thickness incl. case, mm (sets the lip height)
phone_l  = 162;      // phone length incl. case, mm (preview only; the tray is shorter than the phone)
cam_from = 114;      // camera bump starts this far up from the phone's bottom edge
cam_to   = 152;      // ...and ends here (preview only)
cam_clear = 4;       // gap between the end of the tray and the start of the camera bump

// ---------- clamp ----------
table_max = 35;      // thickest table edge the clamp accepts, mm //28.575
cw        = 36;      // clamp width along the table edge
jaw_d     = 45;      // how far the jaws reach onto the table
jaw_t     = 10;      // jaw thickness
spine_t   = 10;      // back wall thickness
gap       = table_max + 5;
bolt6     = 6.6;     // M6 clearance
nut6_af   = 10.4;    // M6 nut across flats + clearance
nut6_h    = 5.5;

// ---------- post ----------
tube_o = 20;  tube_i = 16;  tube_l = 150;      // outer tube (part of the clamp)
rod_o  = tube_i - 0.4;  rod_i = rod_o - 4;  rod_l = 220;   // inner rod, hollow
pin_d  = 4.4;  pin_from_top = 15;  pin_pitch = 20;  pin_first = 33;  pin_n = 6;   // pin_first puts the 6 holes at extensions 0,20,..,100
ear_t = 5;  ear_r = rod_o / 2;  ear_gap = 8.4;  ear_rise = 16;  bolt4 = 4.4;      // ears flush with the rod so the post prints on its side

// ---------- tray ----------
rail_w  = 8;   plate_t = 4;
tray_l  = 95;        // frame length. Must end below the camera bump of every phone you want to fit: bumps start
                     // around 95-100 mm up on small phones (131-147 mm long) and 105-115 mm on large ones, so 95
                     // clears nearly everything. Stability does not depend on it because of the hook below.
lip_h   = phone_t + 3;   lip_t = 3;   cable_gap = 16;   // lips 3 mm taller than the phone: 2 mm hook + 1 mm clearance over the face
hook    = 3;         // the bottom lip curls over the phone's face by this much, so the phone cannot lift off the
                     // frame even when its centre of mass is past the end bar (long phone on a short tray). 0 = no hook
hook_t  = 2;         // hook thickness
cross_z = (tray_l - rail_w) / 2;   // middle bar, so the phone rests on three bars: bottom, middle, and one just below the camera
tab_t   = 8;   tab_r = 7;   tab_back = 12;   tab_drop = 14;   // hinge axis sits on the lip side of the plate, below its bottom edge

// ---------- preview pose ----------
ext  = 60;   // rod extension in the assembly preview, 0..100 in steps of 20
tilt = 45;   // tray tilt from vertical in the preview, 0..90
screw_gap = 0;   // preview only: how far the printed screw's tip is backed off from the table underside

$fn = 48;
iw = phone_w + 2;              // tray inner width
tw = iw + 2 * rail_w;          // tray outer width
hinge_hole = all_printed ? thr_d_t + thr_clear : bolt4;   // ears and tab

// Printed thread: a circle offset from the axis, twisted one turn per pitch. Major diameter d,
// minor diameter 0.6 d. Cut the mating hole with the same call and clearance = thr_clear.
module thread(d, pitch, len, clearance = 0) {
    e = 0.2 * d;
    linear_extrude(height = len, twist = -360 * len / pitch, slices = ceil(len * 6), convexity = 10)
        translate([e, 0]) circle(d = d - 2 * e + clearance);
}

// =====================================================================
// parts (design coordinates)
// =====================================================================

// Table top is z=0, table edge at x=0, table extends toward +x. Spine sits at x in [-spine_t, 0].
module clamp() {
    difference() {
        union() {
            // upper jaw, spine, lower jaw
            translate([-spine_t, -cw/2, 0]) cube([spine_t + jaw_d, cw, jaw_t]);
            translate([-spine_t, -cw/2, -(gap + jaw_t)]) cube([spine_t, cw, gap + 2 * jaw_t]);
            translate([-spine_t, -cw/2, -(gap + jaw_t)]) cube([spine_t + jaw_d, cw, jaw_t]);
            // outer tube rising from the upper jaw
            translate([-spine_t, -tube_o/2, jaw_t]) cube([tube_o, tube_o, tube_l]);
            // gusset between tube and jaw on the table side
            hull() {
                translate([-spine_t + tube_o - 1, -tube_o/2, jaw_t]) cube([1, tube_o, 35]);
                translate([-spine_t + tube_o - 1, -tube_o/2, jaw_t]) cube([22, tube_o, 1]);
            }
            // all-printed: block under the lower jaw so the female thread has 4 turns engaged instead of 2.5
            // (a full-width block, not a round boss, so it sits flat on the bed when the clamp prints on its side)
            if (all_printed) translate([jaw_d - 12 - 12, -cw/2, -(gap + jaw_t) - boss_h]) cube([24, cw, boss_h + 1]);
        }
        // tube bore, closed 2 mm above the jaw
        translate([-spine_t + (tube_o - tube_i)/2, -tube_i/2, jaw_t + 2]) cube([tube_i, tube_i, tube_l]);
        // pin hole through the tube, along y
        translate([-spine_t + tube_o/2, 0, jaw_t + tube_l - pin_from_top]) rotate([90, 0, 0]) cylinder(d = pin_d, h = tube_o + 2, center = true);
        // clamp screw through the lower jaw: threaded hole (all printed) or M6 clearance hole + nut pocket
        if (all_printed) {
            translate([jaw_d - 12, 0, -(gap + jaw_t) - boss_h - 1]) thread(thr_d_c, thr_pitch_c, jaw_t + boss_h + 2, thr_clear);
        } else {
            translate([jaw_d - 12, 0, -(gap + jaw_t) - 1]) cylinder(d = bolt6, h = jaw_t + 2);
            translate([jaw_d - 12, 0, -(gap + jaw_t) - 1]) cylinder(d = nut6_af / cos(30), h = nut6_h + 1, $fn = 6);
        }
    }
}

// Rod from z=0 to rod_l, ears above it, hinge axis along y at z = rod_l + ear_rise.
module post() {
    difference() {
        union() {
            translate([-rod_o/2, -rod_o/2, 0]) cube([rod_o, rod_o, rod_l]);
            for (s = [-1, 1]) translate([0, s * (ear_gap/2 + ear_t/2), 0])
                hull() {
                    translate([-rod_o/2, -ear_t/2, rod_l - 1]) cube([rod_o, ear_t, 1]);
                    translate([0, 0, rod_l + ear_rise]) rotate([90, 0, 0]) cylinder(r = ear_r, h = ear_t, center = true);
                }
        }
        // hollow, leaving 10 mm solid at the top
        translate([-rod_i/2, -rod_i/2, -1]) cube([rod_i, rod_i, rod_l - 10 + 1]);
        // pin holes along y
        for (i = [0 : pin_n - 1]) translate([0, 0, pin_first + i * pin_pitch]) rotate([90, 0, 0]) cylinder(d = pin_d, h = rod_o + 2, center = true);
        // hinge bolt
        translate([0, 0, rod_l + ear_rise]) rotate([90, 0, 0]) cylinder(d = hinge_hole, h = rod_o + 2 * ear_t + 2, center = true);
    }
}

// Plate occupies x in [0, plate_t]; the phone lies on the -x face. Hinge axis along y at (x = -tab_back, z = -tab_drop),
// i.e. on the lip side, so lips and tab all point the same way and the tray prints flat without supports.
module tray() {
    difference() {
        union() {
            // frame: two rails and three bars (bottom, middle, and the end bar just below the camera bump)
            for (s = [-1, 1]) translate([0, s * (iw/2 + rail_w/2) - rail_w/2, 0]) cube([plate_t, rail_w, tray_l]);
            translate([0, -tw/2, 0]) cube([plate_t, tw, rail_w]);
            translate([0, -tw/2, cross_z]) cube([plate_t, tw, rail_w]);
            translate([0, -tw/2, tray_l - rail_w]) cube([plate_t, tw, rail_w]);
            // side lips
            for (s = [-1, 1]) translate([-lip_h, s * (iw/2 + lip_t/2) - lip_t/2, 0]) cube([lip_h + plate_t, lip_t, tray_l]);
            // bottom lip, split for a charging cable, with a hook curling over the phone's bottom edge
            for (s = [-1, 1]) translate([-lip_h, s > 0 ? cable_gap/2 : -tw/2, 0]) {
                cube([lip_h + plate_t, tw/2 - cable_gap/2, lip_t]);
                cube([hook_t, tw/2 - cable_gap/2, lip_t + hook]);
            }
            // hinge tab
            translate([0, -tab_t/2, 0]) hull() {
                cube([plate_t, tab_t, rail_w]);
                translate([-tab_back, 0, -tab_drop]) rotate([-90, 0, 0]) cylinder(r = tab_r, h = tab_t);
            }
        }
        translate([-tab_back, 0, -tab_drop]) rotate([90, 0, 0]) cylinder(d = hinge_hole, h = tab_t + 2, center = true);
    }
}

if (tray_l > cam_from - cam_clear) echo(str("WARNING: tray_l ", tray_l, " reaches under the camera bump (starts at ", cam_from, ")"));

// Ghost of the phone lying in the tray (preview only, never exported): body plus the camera bump band.
module ghost_phone() {
    %translate([-phone_t, -phone_w/2, lip_t]) cube([phone_t, phone_w, phone_l]);
    %translate([-phone_t - 2, -phone_w/2, lip_t + cam_from]) cube([2, phone_w, cam_to - cam_from]);
}

// Presses onto the M6 bolt's hex head (10 mm across flats).
module knob() {
    difference() {
        union() {
            cylinder(d = 30, h = 8);
            for (a = [0 : 60 : 300]) rotate(a) translate([16, 0, 0]) cylinder(d = 7, h = 8);
        }
        translate([0, 0, 3.5]) cylinder(d = nut6_af / cos(30), h = 10, $fn = 6);
    }
}

module pin() {
    cylinder(d = pin_d - 0.4, h = tube_o + 6);
    cylinder(d = 9, h = 2.5);
}

// ---- all-printed hardware ----
screw_len = gap + jaw_t + 5;   // reaches a 15 mm table edge when fully in, 40 mm when backed out

// Clamp screw: knob head, then thread. Prints head down.
module screw() {
    difference() {
        union() {
            cylinder(d = 30, h = 8);
            for (a = [0 : 60 : 300]) rotate(a) translate([16, 0, 0]) cylinder(d = 7, h = 8);
        }
    }
    translate([0, 0, 8]) thread(thr_d_c, thr_pitch_c, screw_len);
    translate([0, 0, 8 + screw_len]) cylinder(d1 = thr_d_c * 0.7, d2 = 6, h = 3);   // blunt tip
}

// Tilt bolt: flat head with a bar to grip, then thread through tab, ears and nut.
module tilt_bolt() {
    cylinder(d = 16, h = 3);
    translate([-7, -2.5, 3]) cube([14, 5, 4]);
    translate([0, 0, 3]) thread(thr_d_t, thr_pitch_t, tab_t + 2 * ear_t + 8);
}

module wing_nut() {
    difference() {
        union() {
            cylinder(d = 14, h = 6);
            for (s = [-1, 1]) hull() {
                cylinder(d = 8, h = 6);
                translate([s * 12, 0, 0]) cylinder(d = 5, h = 6);
            }
        }
        translate([0, 0, -1]) thread(thr_d_t, thr_pitch_t, 8, thr_clear);
    }
}

// =====================================================================
// assembly preview
// =====================================================================
module assembly() {
    %translate([0, -80, -30]) cube([200, 160, 30]);   // table edge, ghosted
    clamp();
    translate([-spine_t + tube_o/2, 0, jaw_t + 2 + ext]) {
        post();
        translate([0, 0, rod_l + ear_rise]) rotate([0, tilt, 0]) translate([tab_back, 0, tab_drop]) { tray(); ghost_phone(); }
    }
    if (all_printed) translate([jaw_d - 12, 0, -30 - screw_gap - (8 + screw_len + 3)]) screw();   // tip seated on the 30 mm ghost table
    else translate([jaw_d - 12, 0, -(gap + jaw_t) - 8]) knob();
}

// =====================================================================
// print orientations
// =====================================================================
module print_clamp() { rotate([90, 0, 0]) clamp(); }                 // C profile on the bed, tube lying flat
module print_post()  { rotate([0, 90, 0]) post(); }                  // rod on its side, ears standing on edge, bolt hole horizontal
module print_tray()  { rotate([0, 90, 0]) tray(); }                  // frame flat, lips and tab pointing up
module print_knob()  { knob(); }
module print_pin()   { rotate([0, 90, 0]) pin(); }

if (part == "assembly") assembly();
else if (part == "clamp") print_clamp();
else if (part == "post")  print_post();
else if (part == "tray")  print_tray();
else if (part == "knob")  print_knob();
else if (part == "pin")   print_pin();
else if (part == "screw")     screw();
else if (part == "tilt_bolt") tilt_bolt();
else if (part == "wing_nut")  wing_nut();
else if (part == "tray_check") { tray(); ghost_phone(); }   // tray with the phone ghosted in, to check the camera clears the frame
else if (part == "tray_section") {   // cut at y = 20 (through the bottom lip, clear of the cable gap and side lips): shows the hook over the phone
    difference() { union() { tray(); ghost_phone(); } translate([-100, -300, -100]) cube([400, 320, 400]); }
}
else if (part == "clamp_section") {   // cutaway through the screw axis: shows the screw threaded into the lower jaw
    difference() {
        union() {
            clamp();
            %translate([0, -80, -30]) cube([200, 160, 30]);
            if (all_printed) translate([jaw_d - 12, 0, -30 - screw_gap - (8 + screw_len + 3)]) screw();
        }
        translate([-100, -300, -300]) cube([400, 300, 600]);
    }
}
else if (part == "plate") {   // every part in its print orientation, spread out with clear gaps (not a real bed layout)
    translate([0, 160, cw/2]) print_clamp();          // x -10..45,  y 0..215
    translate([110, -40, rod_o/2]) print_post();      // x 110..354, y -49..-31
    translate([140, 90, plate_t]) print_tray();       // x 119..290, y 42..138
    translate([340, 230, 0]) print_pin();
    if (all_printed) {
        translate([140, 240, 0]) screw();
        translate([210, 240, 0]) tilt_bolt();
        translate([275, 240, 0]) wing_nut();
    } else translate([210, 240, 0]) print_knob();
}
