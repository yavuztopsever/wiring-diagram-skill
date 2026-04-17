# /// script
# requires-python = ">=3.11"
# dependencies = ["drawsvg>=2.3"]
# ///
"""Fender Jazz Bass — V / V / T  +  DPDT series/parallel MOD  +  DPDT kill switch.

Canonical reference diagram for the `wiring-diagram` skill. Rendered via the
routing primitives in `wiring.py`:

  - `GroundRail`        visible horizontal ground bus (instead of a star dot)
  - `wire_path()`       explicit waypoints — every wire steered around the
                        pot & switch bodies; no wire cuts through a component
  - staggered z-routes  (neck-gnd @ y=400, bridge-hot @ y=440) so parallel
                        horizontal runs don't visually merge
  - terminals approached from the body edge nearest the target terminal,
                        not from the opposite side (no wires punched through
                        full switch bodies)
  - `assert_complete()` sanity check — every pickup lead and jack tab wired

Color coding for mode-dependent wires
-------------------------------------
To make it visually clear which wires are ALWAYS-ON chassis grounds (the
8 wires that exist in every passive bass — pot casings, lug 1s, jack
sleeve, etc.) vs which are SWITCH-ROUTED throws active only in one mode,
the example uses these colors:

  black  ─ always-on chassis ground  (pot casings, vol-pot lug 1s,
           jack sleeve, tone-cap return, bridge-pickup ground lead)
  orange ─ MOD parallel-only throws  (T1→GND, T2→Vol-B)  — conducts
           only when the MOD switch is in parallel position
  blue   ─ MOD series-only jumper  (T5↔T6)  — conducts only when the
           MOD switch is in series position
  red    ─ KILL kill-only throws  (T4, T6)  — conducts only when
           the KILL switch is engaged
  gold   ─ always-on signal / hot bus
  white  ─ pickup hot lead (Fender convention)

Of the 10 wires that terminate on the ground rail, 8 are ALWAYS-ON
(black) and only 2 are MODE-DEPENDENT (MOD T1 = orange, KILL T6 = red).
The diagram is NOT routing signal to ground — it's re-routing pickup
leads between meaningful destinations.

Circuit summary (unchanged from v1, still electrically correct)
---------------------------------------------------------------

    Parallel (DPDT MOD up):
        Neck hot    ─► Vol-N lug 3
        Neck gnd    ─► MOD T3 ─── T1 ─► GND
        Bridge hot  ─► MOD T4 ─── T2 ─► Vol-B lug 3
        Bridge gnd  ─► GND

    Series (DPDT MOD down):
        Neck hot    ─► Vol-N lug 3                (unchanged)
        Bridge gnd  ─► GND                        (unchanged)
        Neck gnd    ─► MOD T3 ─── T5 ═════ T6 ─── T4 ─► Bridge hot
        (series-link jumper T5↔T6 ties neck-gnd to bridge-hot)

    Kill switch:
        Normal:  bus ─► KILL T3 ─── T1 ─► Jack tip      (signal through)
                 KILL T4 ═ Jack tip  (but T4→T2 open, no effect)

        Kill:    bus ─► KILL T3 ─── T5 (dead-end)       (signal blocked)
                 KILL T4 ─── T6 ─► GND                  (tip shorted)

    Volume pots, both standard voltage-divider wiring:
        lug 3 = pickup hot in,  lug 2 = wiper → bus,  lug 1 = GND, casing = GND

    Tone pot (Fender cap-on-outer-lug style):
        bus → lug 2 (wiper).  lug 1 → cap → GND.  lug 3 unused.
        Knob CW = bright, CCW = dark.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wiring as w


# ---------------------------------------------------------------- canvas ---

d = w.Diagram(
    width=1320,
    height=1120,
    title="Fender Jazz Bass — Series/Parallel DPDT + Kill DPDT",
    subtitle="Vol / Vol / Tone   |   250kA pots   |   0.047\u00b5F tone cap   |   passive",
)


# ------------------------------------------------------------ components ---

# Pickups — top row. Placed so their x columns are clear of the pot bodies
# below them (pickup hot/gnd leads drop into the column between pots).
neck   = d.add(w.SingleCoil(270, 210, "Neck Pickup",   poles=4))
bridge = d.add(w.SingleCoil(490, 210, "Bridge Pickup", poles=4))

# Control row — pots + switches on a shared y centerline.
vol_n = d.add(w.Pot(280, 540, "Vol (Neck)",   value="250kA"))
vol_b = d.add(w.Pot(440, 540, "Vol (Bridge)", value="250kA"))
tone  = d.add(w.Pot(600, 540, "Tone",         value="250kA"))
mod   = d.add(w.DPDT(780, 540, "MOD  (Series / Parallel)", throws=2))
kill  = d.add(w.DPDT(940, 540, "KILL  (Stutter)",          throws=2))
jack  = d.add(w.Jack(1140, 540, "Output Jack", kind="TS"))

# Tone cap hangs below the tone pot.
cap = d.add(w.Capacitor(600, 720, "0.047\u00b5F", label="Tone Cap"))

# Visible ground bus rail below everything. All grounds TAP this rail.
rail = d.add(w.GroundRail(y=820, x_start=200, x_end=1240,
                           ground_at="left", label="Chassis GND"))


# ------------------------------------------------------------ conventions ---

HOT    = w.WireColor.HOT                  # golden — signal / hot bus
GROUND = w.WireColor.GROUND               # black  — ALWAYS-ON chassis ground
PK_HOT = w.WireColor.PICKUP_HOT_WHITE     # white  — pickup hot lead (Fender)
PK_GND = w.WireColor.PICKUP_GROUND        # black  — pickup ground lead

# ── Mode-dependent wire colors ─────────────────────────────────────────────
# These distinguish wires that only carry current in a specific switch
# position.  They address a common reader question — "doesn't the switch
# just dump everything to ground?" — by making it visually obvious which
# wires are ALWAYS-ON chassis grounds vs which are SWITCH-ROUTED throws
# active only in one mode.
PARALLEL = "#d97706"   # orange — MOD throws active only in PARALLEL position
SERIES   = "#2b6cb0"   # blue   — MOD jumper active only in SERIES position
KILL_RED = "#dc2626"   # red    — KILL throws active only when kill ENGAGED


# Horizontal-run y-bands (kept unique per wire to prevent visual merging):
#   y=400  — neck-gnd    run to MOD T3
#   y=440  — bridge-hot  run to MOD T4
#   y=470  — switch-top  exit band (MOD T2 exit, KILL T1 exit)
#   y=610  — switch-bot  exit band (KILL T4 exit)
#   y=660  — output bus  (vol wipers + tone input + kill input)


# ============================================================== PICKUPS ===

# Neck hot → Vol-N lug 3. Lug 3 sits at (310, 592), inside the pot body's
# x-range, so we can't drop straight down. Route east of the body, past
# the bottom, and back west to the lug. Three segments, zero body intrusion.
d.wire_path([
    neck.hot,
    (360, neck.hot[1]),   # right at pickup level (clear of Vol-N)
    (360, 610),           # down past the pot body (pot bottom = y=580)
    (310, 610),           # left to lug 3's column
    vol_n.lug(3),         # up (1 px) into lug 3
], color=PK_HOT)

# Neck-GROUND lead (black lead from the neck pickup) → MOD common T3.
# Horizontal run at y=400 (unique band). Approach T3 from the LEFT —
# 10-unit body intrusion only.
d.wire_path([
    neck.gnd,
    (neck.gnd[0], 400),
    (740, 400),
    (740, 540),
    mod.term(3),
], color=PK_GND, label="neck-GND lead to T3")

# Bridge-HOT lead (white lead from the bridge pickup) → MOD common T4.
# Horizontal run at y=440 (its own band, not y=400). Approach T4 from
# the RIGHT — 10-unit body intrusion only.
d.wire_path([
    bridge.hot,
    (bridge.hot[0], 440),
    (820, 440),
    (820, 540),
    mod.term(4),
], color=PK_HOT, label="bridge-HOT lead to T4")

# Bridge gnd → rail. Straight vertical at x=499.  Crosses:
#   y=400  neck-gnd z-route horizontal  — SAME COLOR (both PK_GND)
#   y=440  bridge-hot z-route horizontal (white)      — different color, OK
#   y=470  MOD T2 → Vol-B horizontal (gold)           — different color, OK
#   y=660  output-bus horizontal (gold)               — different color, OK
# For the same-color crossing at (499, 400) we use wire_with_hops() so the
# bridge-gnd wire draws a small semicircle hop OVER the neck-gnd horizontal.
# Without the hop, two black lines meeting at a point would look connected.
d.wire_with_hops(
    bridge.gnd, rail.tap(bridge.gnd[0]),
    crossings=[(499, 400)],
    color=PK_GND, hop_side="right", hop_size=10,
)


# ================================================================ MOD ===

# MOD T1: wired to GND rail. THROW terminal — only conducts in PARALLEL
# position (T3↔T1 closes → neck-GND reaches GND through this wire).
# COLOR: orange (PARALLEL) so the reader can distinguish it from always-on
# chassis grounds (black).  This wire is NOT a "signal being sent to GND"
# — it's the parallel-mode path for the neck pickup's ground LEAD.
d.wire_path([
    mod.term(1),
    (740, mod.term(1)[1]),
    (740, 810),
    rail.tap(740),
], color=PARALLEL, label="T1: GND  (parallel only)")

# MOD T2: wired to Vol-B lug 3. THROW terminal — only conducts in PARALLEL
# position (T4↔T2 closes → bridge-HOT reaches Vol-B input).  COLOR: orange
# (PARALLEL) so the reader sees which wires are mode-dependent.
d.wire_path([
    mod.term(2),
    (mod.term(2)[0], 470),
    (485, 470),
    (485, 610),
    (vol_b.lug(3)[0], 610),
    vol_b.lug(3),
], color=PARALLEL, label="T2: Vol-B lug 3  (parallel only)")

# MOD series-link jumper: T5 ↔ T6. When the switch is in series position,
# commons T3 and T4 both reach this jumper, which ties neck-GND to
# bridge-HOT — that's the series junction inside the pickup pair.
d.wire(mod.term(5), mod.term(6), color=SERIES, route="direct",
       label="series-link jumper")


# ========================================================= VOLUME POTS ===

# Vol-N lug 1 (CCW) → rail.  Straight vertical — lug 1 sits at (250, 592).
d.wire(vol_n.lug(1), rail.tap(vol_n.lug(1)[0]), color=GROUND, route="orth-v")
# Vol-N casing (pot body ground) → rail.  Casing tab is on the LEFT of the pot.
d.wire(vol_n.casing, rail.tap(vol_n.casing[0]), color=GROUND, route="orth-v")

# Vol-B lug 1 → rail.
d.wire(vol_b.lug(1), rail.tap(vol_b.lug(1)[0]), color=GROUND, route="orth-v")
# Vol-B casing → rail.
d.wire(vol_b.casing, rail.tap(vol_b.casing[0]), color=GROUND, route="orth-v")


# ========================================================= OUTPUT BUS ===

# The bus junction — electrical node where the two volume wipers meet,
# feeding both tone and the kill-switch input. Placed in empty space
# BELOW the pot row (y=660). Offset from x=500 to x=530 so the bridge-gnd
# wire (straight vertical at x=499) does NOT visually intersect the
# junction dot — a reader must not confuse ground with the signal bus.
BUS = (530, 660)

# Both volume-pot wipers drop to the bus.
d.wire(vol_n.lug(2), BUS, color=HOT, route="orth-v")
d.wire(vol_b.lug(2), BUS, color=HOT, route="orth-v")

# Mark the junction with a fat dot so it reads as "these wires are tied".
d.junction(*BUS)
d.note(BUS[0], BUS[1] - 10, "output bus", size=10, anchor="middle", color="#444")


# ================================================================ TONE ===

# Bus → Tone lug 2 (wiper) = signal into the tone branch.
d.wire(BUS, tone.lug(2), color=HOT, route="orth-v")

# Tone lug 1 (CCW end) → Cap.a → Cap.b → rail.  Classic "cap on outer lug"
# tone circuit: knob CW = wiper away from cap end, high pot resistance in
# series with cap → no treble cut.  Knob CCW = wiper at cap end, ~0Ω series,
# cap shunts treble to ground → tone cut.
d.wire(tone.lug(1), cap.a, color=HOT, route="orth-v")
d.wire(cap.b, rail.tap(cap.b[0]), color=GROUND, route="orth-v")

# Tone pot casing → rail.
d.wire(tone.casing, rail.tap(tone.casing[0]), color=GROUND, route="orth-v")

# Lug 3 is intentionally left floating in this wiring.
d.note(tone.lug(3)[0] + 10, tone.lug(3)[1] + 5,
       "lug 3 unused", size=9, color="#999")


# ============================================================ KILL SW ===

# Output bus → KILL common T3 (pole 1 common, the signal input of the
# kill switch). Approach T3 from the LEFT for a clean entry.
d.wire_path([
    BUS,
    (900, BUS[1]),
    (900, 540),
    kill.term(3),
], color=HOT, label="signal into T3")

# KILL T1: wired to Jack tip. THROW terminal carrying the signal from
# common T3 to the jack tip in normal position. Floating in kill position.
d.wire_path([
    kill.term(1),
    (kill.term(1)[0], 455),
    (jack.tip[0], 455),
    jack.tip,
], color=HOT, label="T1: jack tip")

# KILL T4: pole-2 common, wired to jack tip. In NORMAL position T4↔T2
# closes but T2 is unused, so this wire does nothing audible. In KILL
# position T4↔T6 closes, and since T6 is on GND, jack tip gets pulled to
# ground through this wire + T6 → the "short to GND" action that kills
# signal with no pop.  COLOR: red (KILL) because its conducting role is
# only in the kill-engaged position.
d.wire_path([
    kill.term(4),
    (980, kill.term(4)[1]),
    (980, 610),
    (jack.tip[0], 610),
    jack.tip,
], color=KILL_RED, label="T4: jack tip  (carries tip\u2192GND when kill ON)")

# KILL T6: wired to GND rail.  THROW terminal — only conducts when KILL
# ENGAGED (T4↔T6 closes, shorting jack tip to GND).  Floating in normal
# position.  COLOR: red (KILL) to make the distinction from always-on
# chassis grounds (black) visible.  Exit DOWN to stay clear of the bus
# vertical at x=900.
d.wire_path([
    kill.term(6),
    (kill.term(6)[0], 810),
    rail.tap(kill.term(6)[0]),
], color=KILL_RED, label="T6: GND  (kill only)")

# Unused kill throws — explicitly called out so a reader knows they're not
# forgotten connections.
d.note(kill.term(5)[0] - 10, kill.term(5)[1] + 18,
       "T5 unused (dead-end)", size=8, anchor="end", color="#999")
d.note(kill.term(2)[0] + 10, kill.term(2)[1] - 8,
       "T2 unused", size=8, color="#999")


# ================================================================ JACK ===

# Jack sleeve → rail.  Straight vertical.
d.wire(jack.sleeve, rail.tap(jack.sleeve[0]), color=GROUND, route="orth-v")


# ============================================================== LEGEND ===

# Legend placed in the open band between the tone cap and the rail, far
# LEFT of the jack-sleeve → rail wire at x=1194.  Previous position at
# x=1030 crossed that wire; the legend box would occlude the ground lead.
d.legend(
    20, 660,
    [
        (HOT,      "Signal / hot bus  (always-on)"),
        (PK_HOT,   "Pickup hot lead  (Fender white)"),
        (GROUND,   "Always-on chassis ground  (in every bass)"),
        (PARALLEL, "MOD parallel-only throws  (T1, T2)"),
        (SERIES,   "MOD series-only jumper  (T5\u2194T6)"),
        (KILL_RED, "KILL kill-only throws  (T4, T6)"),
    ],
)


# ============================================================ TRUTH TABLES ===

# Each DPDT has two positions (throws A and B). The switch's action is
# easier to reason about by LISTING what closes in each position than by
# "up/down" lever direction — so here are the per-switch operating tables.

d.truth_table(
    80, 878,
    "MOD switch  —  Series / Parallel toggle",
    [
        ("POS A",
         "T3\u2194T1 closes (neck-GND meets GND rail)  +  T4\u2194T2 closes (bridge-HOT meets Vol-B.lug 3)"),
        ("",
         "\u21d2  PARALLEL: each pickup feeds its own volume pot  =  standard J-Bass V/V/T"),
        ("POS B",
         "T3\u2194T5 and T4\u2194T6 close simultaneously; the T5\u2194T6 jumper ties both commons together"),
        ("",
         "\u21d2  neck-GND  =  bridge-HOT  (the series junction inside the coil pair)"),
        ("",
         "\u21d2  SERIES: coils joined end-to-end, output via Vol-N. Hotter, mid-forward."),
    ],
    width=1160,
)

d.truth_table(
    80, 994,
    "KILL switch  —  Stutter / signal interrupt",
    [
        ("POS A",
         "T3\u2194T1 closes (signal continues to jack tip)  +  T4\u2194T2 closes (T2 unused, tip NOT shorted)"),
        ("",
         "\u21d2  NORMAL: signal passes through to the jack"),
        ("POS B",
         "T3\u2194T5 closes (signal dead-ends at unused T5)  +  T4\u2194T6 closes (jack tip \u2192 GND via T6)"),
        ("",
         "\u21d2  KILL: hot path broken AND tip shorted to ground  =  complete silence, no pop"),
    ],
    width=1160,
)

# A compact conventions line at the very bottom.
d.note(
    50, 1095,
    "Pot lugs (viewed from the BACK of the pot): 1 = CCW end, 2 = wiper, 3 = CW end.  "
    "Volume pots wired hot\u2192lug 3, wiper\u2192out, lug 1\u2192GND, casing (\u201cGND\u201d tab on the pot)\u2192GND.  "
    "DPDT: terminals 3 & 4 are the pole commons; 1, 2 = throw A; 5, 6 = throw B. Both poles switch together.",
    size=10, color="#555",
)


# ========================================================== validation ===

# Catch any pickup lead or jack tab that got left dangling.
warnings = d.assert_complete()
if warnings:
    sys.stderr.write(f"[wiring] {len(warnings)} completion warnings above.\n")


# =================================================================== save ===

out = Path(__file__).with_suffix(".svg")
d.save_svg(out)
print(f"wrote {out}  ({out.stat().st_size} bytes)")
