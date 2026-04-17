# /// script
# requires-python = ">=3.11"
# dependencies = ["drawsvg>=2.3"]
# ///
"""Fender Jazz Bass — Parallel / Kill / Series with ONE DPDT-ON-OFF-ON switch.

This is the v0.2 canonical example for the `wiring-diagram` skill.  It
replaces the previous v0.1 two-DPDT design with an elegant single-switch
mod: one DPDT-ON-OFF-ON whose three physical positions map to three
electrical modes:

    UP      (throw A closed)     →  PARALLEL  (standard Jazz Bass V/V/T)
    MIDDLE  (both poles OFF)     →  KILL      (both pickups disconnected)
    DOWN    (throw B closed)     →  SERIES    (two coils summed via
                                                T5-T6 jumper)

How the middle position kills signal
------------------------------------
Putting the switch in the middle OFF position opens BOTH poles
simultaneously.  With `T3 = neck.gnd` (pole-1 common) and `T4 = bridge.hot`
(pole-2 common) both floating:

  - Bridge pickup: bridge.gnd is still tied to GND, but bridge.hot floats.
    The coil has no complete current path → zero signal reaches anywhere.
  - Neck  pickup: neck.hot is still tied to Vol-N.lug(3), but neck.gnd
    floats.  Again no complete current path through the coil → Vol-N.lug(3)
    sits at ~0 V (pulled down by the pot resistance to lug 1/GND).

Net: BUS → jack.tip → amp all sit at ~0 V = silence.  No separate kill
switch needed; the "absence of closure" in the middle position IS the
kill.  (Minor trade-off vs a dedicated hard-kill DPDT: the jack tip is
left floating at 0 V rather than actively shorted to GND, so there's no
hard bleed path for cable-capacitance transients.  In practice it's
inaudible.)

Color coding (mode-dependent wires)
-----------------------------------
  black   — always-on chassis ground (pot casings, lug 1 grounds, jack
            sleeve, tone-cap return, bridge-pickup ground lead)
  gold    — always-on signal / hot bus
  white   — pickup hot lead (Fender convention, dark-outlined)
  orange  — MOD parallel-only throws (T1 → GND,  T2 → Vol-B.lug 3)
            conducts only when switch is UP
  blue    — MOD series-only jumper (T5 ↔ T6)
            conducts only when switch is DOWN

Of the 8 wires that terminate on the ground rail, 7 are ALWAYS-ON
chassis grounds; the one exception is MOD-T1 (orange), a parallel-only
path for the neck pickup's ground lead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wiring as w


# ---------------------------------------------------------------- canvas ---

d = w.Diagram(
    width=1320,
    height=1120,
    title="Fender Jazz Bass — Parallel / Kill / Series  (one DPDT-ON-OFF-ON)",
    subtitle="Vol / Vol / Tone   |   250kA pots   |   0.047\u00b5F tone cap   |   passive",
)


# ------------------------------------------------------------ components ---

# Pickups — top row.
neck   = d.add(w.SingleCoil(270, 210, "Neck Pickup",   poles=4))
bridge = d.add(w.SingleCoil(490, 210, "Bridge Pickup", poles=4))

# Control row.  Jack shifts LEFT to fill the space vacated by the removed
# second DPDT.
vol_n = d.add(w.Pot(280, 540, "Vol (Neck)",   value="250kA"))
vol_b = d.add(w.Pot(440, 540, "Vol (Bridge)", value="250kA"))
tone  = d.add(w.Pot(600, 540, "Tone",         value="250kA"))

# The only switch in the circuit.  throws=3 ⇒ ON-OFF-ON.
mod   = d.add(w.DPDT(780, 540,
                     "MOD  (Parallel / Kill / Series)",
                     throws=3))

jack  = d.add(w.Jack(960, 540, "Output Jack", kind="TS"))

# Tone cap hangs below the tone pot.
cap = d.add(w.Capacitor(600, 720, "0.047\u00b5F", label="Tone Cap"))

# Visible ground bus rail below everything.
rail = d.add(w.GroundRail(y=820, x_start=200, x_end=1060,
                           ground_at="left", label="Chassis GND"))


# ------------------------------------------------------------ conventions ---

HOT      = w.WireColor.HOT                 # gold   — always-on signal
GROUND   = w.WireColor.GROUND              # black  — always-on chassis ground
PK_HOT   = w.WireColor.PICKUP_HOT_WHITE    # white  — pickup hot lead
PK_GND   = w.WireColor.PICKUP_GROUND       # black  — pickup ground lead
PARALLEL = "#d97706"                       # orange — parallel-only throws
SERIES   = "#2b6cb0"                       # blue   — series-only jumper


# ============================================================== PICKUPS ===

# Neck hot → Vol-N.lug(3). Detour around Vol-N body.
d.wire_path([
    neck.hot,
    (360, neck.hot[1]),
    (360, 610),
    (310, 610),
    vol_n.lug(3),
], color=PK_HOT)

# Neck-GROUND lead → MOD common T3. y=400 band.
d.wire_path([
    neck.gnd,
    (neck.gnd[0], 400),
    (740, 400),
    (740, 540),
    mod.term(3),
], color=PK_GND, label="neck-GND lead to T3")

# Bridge-HOT lead → MOD common T4. y=440 band (separate from y=400).
d.wire_path([
    bridge.hot,
    (bridge.hot[0], 440),
    (820, 440),
    (820, 540),
    mod.term(4),
], color=PK_HOT, label="bridge-HOT lead to T4")

# Bridge gnd → rail.  Straight vertical at x=499.  Hop over neck-gnd
# horizontal at y=400 since both are black.
d.wire_with_hops(
    bridge.gnd, rail.tap(bridge.gnd[0]),
    crossings=[(499, 400)],
    color=PK_GND, hop_side="right", hop_size=10,
)


# ============================================================ MOD DPDT ===

# T1 → GND rail.  PARALLEL-ONLY: conducts only when switch is UP (throw A).
d.wire_path([
    mod.term(1),
    (740, mod.term(1)[1]),
    (740, 810),
    rail.tap(740),
], color=PARALLEL, label="T1: GND  (parallel only)")

# T2 → Vol-B.lug(3).  PARALLEL-ONLY.
d.wire_path([
    mod.term(2),
    (mod.term(2)[0], 470),
    (485, 470),
    (485, 610),
    (vol_b.lug(3)[0], 610),
    vol_b.lug(3),
], color=PARALLEL, label="T2: Vol-B lug 3  (parallel only)")

# Series-link jumper T5 ↔ T6.  SERIES-ONLY: conducts only when switch is
# DOWN (throw B), joining neck-GND to bridge-HOT via the commons.
d.wire(mod.term(5), mod.term(6), color=SERIES, route="direct",
       label="series-link  (series only)")


# ========================================================= VOLUME POTS ===

d.wire(vol_n.lug(1), rail.tap(vol_n.lug(1)[0]), color=GROUND, route="orth-v")
d.wire(vol_n.casing, rail.tap(vol_n.casing[0]), color=GROUND, route="orth-v")
d.wire(vol_b.lug(1), rail.tap(vol_b.lug(1)[0]), color=GROUND, route="orth-v")
d.wire(vol_b.casing, rail.tap(vol_b.casing[0]), color=GROUND, route="orth-v")


# ========================================================= OUTPUT BUS ===

# Bus junction — where both volume-pot wipers meet, and where the signal
# continues on to the jack tip (no kill switch in this design).
BUS = (530, 660)

d.wire(vol_n.lug(2), BUS, color=HOT, route="orth-v")
d.wire(vol_b.lug(2), BUS, color=HOT, route="orth-v")
d.junction(*BUS)
d.note(BUS[0], BUS[1] - 10, "output bus", size=10, anchor="middle", color="#444")


# ================================================================ TONE ===

d.wire(BUS, tone.lug(2), color=HOT, route="orth-v")
d.wire(tone.lug(1), cap.a, color=HOT, route="orth-v")
d.wire(cap.b, rail.tap(cap.b[0]), color=GROUND, route="orth-v")
d.wire(tone.casing, rail.tap(tone.casing[0]), color=GROUND, route="orth-v")
d.note(tone.lug(3)[0] + 10, tone.lug(3)[1] + 5,
       "lug 3 unused", size=9, color="#999")


# ============================================================== OUTPUT ===

# BUS → jack tip, direct.  In the middle (kill) position the signal at
# BUS is ~0 V because both pickups are electrically disconnected at MOD,
# so jack tip sits at 0 V = silent.
d.wire_path([
    BUS,
    (BUS[0] + 100, BUS[1]),        # east of bus junction
    (jack.tip[0], BUS[1]),         # horizontal to jack column
    jack.tip,
], color=HOT, label="BUS \u2192 jack tip")

# Jack sleeve → rail.
d.wire(jack.sleeve, rail.tap(jack.sleeve[0]), color=GROUND, route="orth-v")


# ============================================================== LEGEND ===

d.legend(
    20, 660,
    [
        (HOT,      "Signal / hot bus  (always-on)"),
        (PK_HOT,   "Pickup hot lead  (Fender white)"),
        (GROUND,   "Always-on chassis ground  (in every bass)"),
        (PARALLEL, "MOD parallel-only throws  (T1, T2)"),
        (SERIES,   "MOD series-only jumper  (T5\u2194T6)"),
    ],
)


# ============================================================ TRUTH TABLE ===

d.truth_table(
    80, 870,
    "MOD switch (DPDT ON-OFF-ON)  —  all three operating modes",
    [
        ("UP",
         "T3\u2194T1 closes (neck-GND meets GND rail)  +  T4\u2194T2 closes (bridge-HOT meets Vol-B.lug 3)"),
        ("",
         "\u21d2  PARALLEL: each pickup feeds its own vol pot  =  standard J-Bass V/V/T"),
        ("MIDDLE",
         "NOTHING closes.  Both commons (T3, T4) are floating.  Pickups have no complete current path through their coils."),
        ("",
         "\u21d2  KILL: both pickups electrically disconnected; BUS \u2248 0 V  \u2192  silent jack tip"),
        ("DOWN",
         "T3\u2194T5 and T4\u2194T6 close simultaneously; T5\u2194T6 jumper ties both commons together"),
        ("",
         "\u21d2  SERIES: neck-GND \u2261 bridge-HOT; coils joined end-to-end, output via Vol-N.  Hotter, mid-forward"),
    ],
    width=1160,
)

# Conventions footer.
d.note(
    50, 1010,
    "Pot lugs (viewed from the BACK of the pot): 1 = CCW end, 2 = wiper, 3 = CW end.  "
    "Volume pots wired hot\u2192lug 3, wiper\u2192out, lug 1\u2192GND, casing (\u201cGND\u201d tab on the pot)\u2192GND.  "
    "DPDT ON-OFF-ON: terminals 3 & 4 are the pole commons; 1, 2 = throw A (UP); 5, 6 = throw B (DOWN); MIDDLE = both poles open.",
    size=10, color="#555",
)
d.note(
    50, 1030,
    "Kill action note: with MOD in MIDDLE the jack tip sits at ~0 V but is NOT hard-shorted to GND.  "
    "A dedicated hard-kill DPDT would actively short tip\u2192GND (cleaner against cable-capacitance pop) — "
    "trade-off here is one switch instead of two.",
    size=10, color="#555",
)


# ========================================================== validation ===

warnings = d.assert_complete()
if warnings:
    sys.stderr.write(f"[wiring] {len(warnings)} completion warnings above.\n")


# =================================================================== save ===

out = Path(__file__).with_suffix(".svg")
d.save_svg(out)
print(f"wrote {out}  ({out.stat().st_size} bytes)")
