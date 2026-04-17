---
name: wiring-diagram
description: Generate electronically accurate guitar and bass wiring diagrams as SVG. Use when the user asks for a wiring diagram, solder diagram, solder layout, or circuit layout for an electric guitar or bass — including Jazz Bass, Stratocaster, Les Paul, Telecaster, P-Bass, ES-335, humbucker coil-split or coil-tap, series/parallel switching, push-pull pots, DPDT mods, phase-reverse, kill switches, blend pots, treble-bleed, or any other passive instrument electronics. Produces top-down Seymour-Duncan / StewMac style diagrams with numbered pot lugs, DPDT terminal grids, color-coded pickup leads, and a visible ground-bus rail, rendered via a Python component library with automatic body-crossing detection.
---

# wiring-diagram

Generate electronically-accurate guitar / bass wiring diagrams as SVG files
using a Python component library (`scripts/wiring.py`). The visual style is
top-down **Seymour-Duncan / StewMac solder layout**, not ladder schematic —
pots shown as circles with numbered lugs, DPDTs as 2×3 terminal grids,
pickups as rectangles with color-coded leads, and a **visible horizontal
ground rail** below the control row.

## When to use this skill

Use it when the user asks for a wiring diagram, solder diagram, or circuit
layout for a **passive electric guitar or bass**. Typical requests:

- "Jazz Bass series/parallel wiring with a DPDT kill switch"
- "Strat 5-way with a push-pull for neck-on-all-positions"
- "Les Paul 50s wiring with coil splits"
- "Tele 4-way with series mode"
- "Coil-tap push-pull on a humbucker"
- "P-Bass with a treble-bleed mod"

**Do NOT use** for: active electronics (preamps, onboard EQ, batteries),
pedals, amplifiers, speaker cabinet wiring, MIDI, general-purpose
electronics, or stompbox schematics. Those need a different tool.

## Skill layout

```
wiring-diagram/
├── SKILL.md                  (this file)
├── scripts/
│   ├── wiring.py             component library — always import this
│   └── examples/
│       └── jazz_bass_series_parallel_dpdt.py
└── references/
    ├── components.md         API reference — every class, every attribute
    ├── dpdt_switch_wiring.md DPDT terminal numbering + 4 classical mods
    ├── common_circuits.md    Node-to-node recipes for common wirings
    └── series_parallel_audit.md  Formal per-wire trace of the J-Bass
                                  series/parallel DPDT mod — use when a
                                  user questions why the switch works
                                  as it does
```

## Generation workflow

1. **Restate the user's request as a terminal-level netlist.** Before writing
   any code, list every wire as `<source.attr> → <destination.attr>`.
   Consult `references/dpdt_switch_wiring.md` for mod recipes and
   `references/common_circuits.md` for full instrument netlists. If you
   can't name every node, stop and ask the user.

2. **Write a standalone Python script** under
   `scripts/examples/<wiring_name>.py`. Start the file with PEP 723 inline
   deps and a sys.path shim so `import wiring` resolves:

   ```python
   # /// script
   # requires-python = ">=3.11"
   # dependencies = ["drawsvg>=2.3"]
   # ///
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
   import wiring as w
   ```

3. **Follow the layout and routing rules below** — they encode what the
   library's collision detector enforces and what reads as a professional
   solder reference.

4. **Run the script** with `uv` (auto-installs `drawsvg` on first run):

   ```bash
   uv run scripts/examples/<wiring_name>.py
   ```

   Any wire that passes through a component body prints a `[wiring] WARNING`
   to stderr with the exact segment coordinates. **Fix every warning before
   delivering the diagram.** Zero warnings = production-ready.

   The script also calls `d.assert_complete()` which lists any pickup lead
   or jack tab that has no wire attached.

5. **Deliver** the SVG path to the user. Mention which modes (up/down) do
   what if there are switches.

---

## Layout rules (non-negotiable)

### L1. Three rows, left-to-right signal flow

```
    y ≈ 210        ┌─ pickups ──┐   ┌─ pickups ──┐
    y ≈ 540        [pot] [pot] [pot] [DPDT] [DPDT] [jack]
    y ≈ 720        [tone cap]
    y ≈ 820        ══════════════ ground rail ══════════════
```

Pickups at the top, control row in the middle, tone caps just below the
control row, ground rail at the bottom. Pickups' x-columns should sit in the
**gaps between pots** so their hot and ground leads drop cleanly without
crossing pot bodies.

### L2. Always use a `GroundRail`, never a lone `Ground`

```python
rail = d.add(w.GroundRail(y=820, x_start=200, x_end=1240,
                           ground_at="left", label="Chassis GND"))
```

A single star-point at one (x, y) forces a dozen wires to fan in — looks
cluttered and implies a physical star at that location. A visible rail
reads as "this horizontal line IS the ground bus, tap it anywhere." Every
ground wire ends with `rail.tap(x)` — typically `rail.tap(source_x)` so the
wire is a straight vertical drop.

### L3. Horizontal-run y-bands — one wire per band

When two wires each need a long horizontal run (typical for z-routes from a
pickup to a switch), put each on its **own unique y-band**. Reserving
bands:

- `y = 400-430`: upper routing band (pickup-level wires heading to switches)
- `y = 440-470`: second upper band
- `y = 470-490`: "switch-top exit" band (for terminals 1/2 that exit UP)
- `y = 610-640`: "switch-bottom exit" band (for terminals 5/6 that exit DOWN)
- `y = 650-680`: output bus band (where vol wipers meet tone and jack)

Pass the y explicitly to `wire()` via `mid_y=...` for z-routes, or use
`wire_path()` with waypoints at the chosen y. **Never** let two separate
wires share the same horizontal y coordinate — they'll visually merge.

---

## Routing rules (the library enforces these)

### R1. Prefer `wire_path()` over `wire(..., route=...)`

`wire()` with `route="orth"/"orth-v"/"z"` is fine for **short, clear runs**
between adjacent components (e.g. pot wiper down to the bus, rail taps).
For anything that crosses a component, use `wire_path()`:

```python
d.wire_path([
    source.attr,
    (x1, y1),        # intermediate waypoint 1
    (x2, y2),        # intermediate waypoint 2
    destination.attr,
], color=w.WireColor.HOT)
```

### R2. Never cross a component body — route around it

Every component has a `.bbox()`. The library warns whenever a wire segment
passes through one (excluding segments that *terminate* in that bbox — i.e.
connecting TO that component). **Every warning must be resolved before
shipping.**

The canonical detour pattern (pickup hot above a pot → pot's lug 3, which
sits inside the pot's x-column):

```python
d.wire_path([
    pickup.hot,
    (pot.x + pot.RADIUS + 20, pickup.hot[1]),  # east of pot's right edge
    (pot.x + pot.RADIUS + 20, pot.lug(3)[1] + 18),  # drop past pot bottom
    (pot.lug(3)[0], pot.lug(3)[1] + 18),       # left to lug column
    pot.lug(3),                                # up into lug
], color=PK_HOT)
```

### R3. Approach switch terminals from the nearest body edge

A DPDT body is 46 wide × 94 tall; terminals 1/2 are top, 3/4 middle, 5/6
bottom. A wire approaching from the **wrong** edge has to cut through the
whole body:

| terminal | nearest edge(s) | approach direction |
|---|---|---|
| T1 (top-left) | top, left | exit UP or LEFT |
| T2 (top-right) | top, right | exit UP or RIGHT |
| T3 (mid-left) | left | exit LEFT |
| T4 (mid-right) | right | exit RIGHT |
| T5 (bot-left) | bottom, left | exit DOWN or LEFT |
| T6 (bot-right) | bottom, right | exit DOWN or RIGHT |

Same rule for pot lugs (approach from the south, never from the north),
jack tabs (approach from the east), cap leads (from horizontally opposite
sides).

### R4. Two wires to the same node via different paths

When pole-1 and pole-2 of a switch both wire to jack tip (common in
kill-switch mods), route them on **different y-bands** and let them both
end at `jack.tip`. Don't try to "save" one wire by jumpering terminals
inside the switch — that obscures the circuit.

```python
d.wire_path([kill.term(1), (kill.term(1)[0], 470),
             (jack.tip[0], 470), jack.tip], color=HOT)  # top band
d.wire_path([kill.term(4), (980, kill.term(4)[1]), (980, 610),
             (jack.tip[0], 610), jack.tip], color=HOT)  # bottom band
```

### R5. Output-bus junctions go in empty space, marked with `d.junction()`

When multiple wires meet at an electrical node that isn't on a component
(classic: the tied volume-pot wipers), pick a coordinate in the control
row's empty band (e.g. `(500, 660)`), route every incoming wire to that
point, and mark it with `d.junction(x, y)` (filled black dot). Add a small
`d.note(...)` label like "output bus" above or below.

### R6. Run `assert_complete()` before saving

```python
d.assert_complete()
d.save_svg(out)
```

Catches unwired pickup leads and jack tabs — a 30-second sanity check that
would otherwise slip through.

### R7. Hop over same-color crossings with `wire_with_hops()`

When two wires cross **and they're the same color** (classic case: two
pickup-ground wires, or two ground-bus wires, both rendered as `#1a1a1a`
black), the standard "no junction dot = not connected" convention fails —
a reader sees two black lines meeting at a point and reads it as a node.

Fix: draw the *hopping* wire with `d.wire_with_hops(...)` so it lifts over
the crossed wire with a small semicircle arc. The arc visually separates
the two wires.

```python
# Bridge-gnd vertical (black) crosses neck-gnd z-route horizontal (black)
# at (499, 400). Use a hop so the crossing reads unambiguously.
d.wire_with_hops(
    bridge.gnd, rail.tap(bridge.gnd[0]),
    crossings=[(499, 400)],
    color=PK_GND, hop_side="right", hop_size=10,
)
```

Only needed for same-color crossings. Different-color crossings (gold ×
black, white × gold, etc.) read fine as bare crosses.

### R8. For every switch, draw a `truth_table` explaining its modes

Readers routinely misread wire labels like `"T1 → GND"` as *"signal flows
into ground here"* — it's actually just *"T1 is physically wired to the
ground rail; whether anything reaches it depends on switch position."*
Avoid the confusion with two tools:

1. **Label each switch-throw wire** with the *destination* the terminal is
   attached to, not an action-arrow. Prefer `"T1: GND rail"` over
   `"T1 → GND"`. Keep arrows only for wires that represent *signal flow
   into the switch* (e.g. `"signal into T3"`).

2. **Add a `d.truth_table(...)`** near every switch listing what closes in
   each position and what that means electrically:

   ```python
   d.truth_table(80, 878, "MOD  —  Series / Parallel toggle", [
       ("POS A",
        "T3↔T1 closes (neck-GND meets GND rail) + T4↔T2 closes (bridge-HOT meets Vol-B.lug 3)"),
       ("",  "⇒ PARALLEL: each pickup feeds its own vol pot = standard J-Bass"),
       ("POS B",
        "T3↔T5 and T4↔T6 close simultaneously; T5↔T6 jumper ties commons"),
       ("",  "⇒ SERIES: coils joined end-to-end, hotter output"),
   ], width=1160)
   ```

   One row per position for "what closes" + one continuation row per
   position for "what that means." Saves every reader from having to
   trace the netlist themselves.

### R9. Two wires must never share the same column or row

If wire A is drawn after wire B in the same column (same x for a vertical
run) or row (same y for a horizontal run) with overlapping extents, A
paints OVER B. The overlapping segment shows only A's color — B appears
to end where the overlap begins.

This is a subtle killer bug. Check: when placing a wire at, say, x=900,
verify no other wire already uses that column in the same y-range.
Typical culprits: switch-throw wires to the ground rail that happen to
share x with a signal-bus vertical in the same area. Move one to an
adjacent column (+/- 25 pixels).

---

## Wire colors (use the `WireColor` constants, always)

| wire | color | constant |
|---|---|---|
| signal / hot bus | golden `#e4a82f` | `WireColor.HOT` |
| ground bus | black `#1a1a1a` | `WireColor.GROUND` |
| pickup hot lead | white (Fender) | `WireColor.PICKUP_HOT_WHITE` |
| pickup ground lead | black | `WireColor.PICKUP_GROUND` |
| shield / bare | grey `#999999` | `WireColor.SHIELD` |
| 4-cond humbucker | `SD_NORTH_START / _FINISH / SOUTH_START / _FINISH` (Seymour Duncan) |
| mod/jumper wires | `"#2b6cb0"` (blue) — distinguishable from signal bus |

Every diagram gets a `d.legend(x, y, entries)` in the bottom-right showing
what each color means.

---

## Pot lug convention

Viewed from the **back** of the pot (shaft away from you):

- **lug 1** = CCW end
- **lug 2** = wiper (middle)
- **lug 3** = CW end

**Standard volume pot**: pickup-hot → lug 3, wiper (lug 2) → output, lug 1
→ ground, casing (`.casing`) → ground.

**Standard tone pot** (Fender cap-on-outer-lug style): signal on lug 2
(wiper), cap from lug 1 to ground, lug 3 unused. Knob CW = bright, CCW =
dark. An alternative is "cap on wiper" (lug 2 → cap → gnd; lug 3 is signal
in, lug 1 unused) — only use if the user explicitly asks.

## DPDT terminal convention

```
[1] [2]    throw A  (connects to commons in one position)
[3] [4]    commons  (the poles' wipers — signal sources)
[5] [6]    throw B  (connects to commons in the other position)
```

The four classical mods all use BOTH poles simultaneously — see
`references/dpdt_switch_wiring.md` for recipes.

## Grounding

- **One `GroundRail` per diagram** — see L2.
- Every pot casing (`pot.casing`) → rail.
- Every pot's lug 1 (when wired as a standard volume pot) → rail.
- Jack sleeve → rail.
- Pickup grounds → rail (either directly or through a DPDT if the mod
  requires it).
- DPDT unused throws → leave floating (don't tie to ground) unless the
  specific mod calls for it.

## Jack

- `.tip` = hot output.
- `.sleeve` = ground (to rail).
- `.ring` (TRS only) — only used for stereo or battery-switching on active
  circuits, which are out of scope for this skill.

---

## The canonical example

`scripts/examples/jazz_bass_series_parallel_dpdt.py` is a complete, verified
implementation of:

> Fender Jazz Bass V/V/T + DPDT series/parallel mod + DPDT kill switch

It demonstrates every rule above (pot numbering, DPDT terminals, wire
colors, ground rail, body-avoiding routing, y-band separation,
`assert_complete`). **Read it before writing your first diagram** — it's
the pattern template. For any new diagram, the quickest start is to copy
this file, rename, and adapt.

## Scope / refusal

- **Passive guitar/bass wiring only.** Refuse (politely, with a short
  explanation) for: amp/preamp circuits, pedals, synthesizers, non-instrument
  electronics, PCB layouts, or anything requiring active components.
- If the user asks for a layout you can't express with the library's
  components (e.g., a specialty switch the library doesn't model), say so
  and offer to (a) add the missing component to `wiring.py`, or (b)
  approximate with an existing switch plus a `d.note()` callout.
