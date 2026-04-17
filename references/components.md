# Component API reference

All coordinates are SVG user units (1 unit ≈ 1 px). Origin is top-left; **y
grows DOWN**. The `(x, y)` passed to each component is its **visual center**
(for `Pot`, `DPDT`, pickups, `Jack`, `Capacitor`, `Ground`).

Every component exposes solder-point attributes (`.lug(n)`, `.term(n)`,
`.hot`, `.gnd`, `.tip`, etc.) that return `(x, y)` tuples. Wire them up with
`Diagram.wire(p_from, p_to, color=..., route=...)`.

---

## `Diagram(width=1100, height=820, title=None, subtitle=None)`

The SVG canvas.

```python
d = Diagram(1320, 940,
            title="Fender Jazz Bass — Series/Parallel DPDT + Kill DPDT",
            subtitle="Vol / Vol / Tone | 250kA pots | 0.047µF tone cap | passive")
```

Methods:

| method | purpose |
|---|---|
| `d.add(component)` | Render a component and register its bbox as an obstacle for future wires. Returns the component for chaining. |
| `d.wire(p_from, p_to, color, width, route, label, mid_y, mid_x)` | Draw a wire using one of the preset routes (see below). Prints a warning if the route passes through a registered obstacle. |
| `d.wire_path(points, color, width, label)` | Draw a wire through explicit waypoints (a list of `(x, y)` tuples or solder-point attrs). Preferred when a preset route would cross a component body. |
| `d.wire_with_hops(p_from, p_to, crossings, color, width, hop_size, hop_side, label)` | Draw a strictly horizontal or vertical wire with small semicircle hops at each listed crossing point. Use when crossing another **same-color** wire — the standard "no dot = not connected" convention fails for same-color crossings. |
| `d.junction(x, y)` | Filled dot marking an electrical junction (wires joining at a point that isn't on a component). |
| `d.crossover(x, y, orientation)` | Small semicircle "hop" marker where a wire crosses another without connecting. Call **before** the wire that does the hopping. |
| `d.note(x, y, text, size, anchor, color)` | Free-floating text annotation. |
| `d.legend(x, y, entries)` | Color-key legend box. `entries = [(color_hex, label), ...]`. |
| `d.truth_table(x, y, title, rows, width)` | Per-switch operating-mode table. `rows = [(left, right), ...]` with an empty `left` for continuation rows. Use one per DPDT/mode switch so readers don't have to trace the netlist. |
| `d.obstacles(exclude=[...])` | Current obstacle list, optionally dropping named components. Pass to `route_around()` if computing waypoints programmatically. |
| `d.assert_complete(strict=False)` | Audit: warn on any unwired pickup lead or jack tab. Returns a list of warning strings. Call BEFORE `save_svg()`. Pass `strict=True` to raise on problems. |
| `d.save_svg(path)` | Write the SVG file. Returns the `Path`. |

### Wire routing (presets for `wire()`)

```
route="direct"  →  straight line
route="orth"    →  L-shape: horizontal first, then vertical
route="orth-v"  →  L-shape: vertical first, then horizontal
route="z"       →  Z-shape: vertical, horizontal (at mid_y), vertical
                   override mid_y with  wire(..., route="z", mid_y=430)
route="z-h"     →  Z-shape: horizontal, vertical (at mid_x), horizontal
                   override mid_x with  wire(..., route="z-h", mid_x=500)
```

Use the `mid_y` / `mid_x` overrides to put each long horizontal run on its
OWN y-band (per SKILL.md rule L3) — otherwise two parallel z-routes merge
into one visual line and misrepresent the circuit.

Use `wire_path()` (explicit waypoints) when a preset route would cut through
a component body. Hand-pick the waypoints so every segment stays in empty
space; the library's collision detector warns if any segment passes through
a registered obstacle whose endpoints aren't on that obstacle.

### `route_around(p_from, p_to, obstacles, clearance=12, prefer="orth")`

Module-level helper (not a method). Returns a waypoint list suitable for
`wire_path()` that detours around single obstacles.

```python
waypoints = w.route_around(mod.term(2), vol_b.lug(3),
                            obstacles=d.obstacles(exclude=[mod, vol_b]))
d.wire_path(waypoints, color=w.WireColor.HOT)
```

Good enough for one-obstacle detours. For dense layouts, pick waypoints by
hand.

### Wire colors

Use the `WireColor` constants — they match industry convention and the
skill's legend:

```
WireColor.HOT                # "#e4a82f" — golden: signal/hot bus
WireColor.GROUND             # "#1a1a1a" — black: ground bus
WireColor.PICKUP_HOT_WHITE   # "#f8f8f8" — Fender white pickup hot lead
WireColor.PICKUP_GROUND      # "#1a1a1a" — black pickup ground lead
WireColor.SHIELD             # "#999999" — bare shield

# Seymour Duncan 4-conductor humbucker:
WireColor.SD_NORTH_START   = "#1a1a1a"  (black)
WireColor.SD_NORTH_FINISH  = "#f8f8f8"  (white)
WireColor.SD_SOUTH_START   = "#d32222"  (red)
WireColor.SD_SOUTH_FINISH  = "#1d8a2f"  (green)
```

For series-link jumpers or other "mod" wires that need to stand out, use
`"#2b6cb0"` (blue) or any unused contrasting hex.

---

## `Pot(x, y, label, value="500kA")`

A potentiometer viewed from the back of its body.

```
                 label
                  │
                 ┌▽────── pot body (circle, R=40)
   GND ──● ──────┤    ╲
                  shaft
                  │
              1  2  3    ← lugs across the bottom (CCW → CW)
```

Attributes:

| attr | returns | meaning |
|---|---|---|
| `.lug(1)` | `(x, y)` | CCW end |
| `.lug(2)` | `(x, y)` | wiper |
| `.lug(3)` | `(x, y)` | CW end |
| `.casing` | `(x, y)` | pot-body ground hook (labeled "GND" on the left of the circle) |
| `.top`    | `(x, y)` | top of the circle (useful as an aesthetic attach point) |

Raises `ValueError` on `.lug(n)` for `n` outside 1..3.

---

## `PushPullPot(x, y, label, value="500kA", throws=2)`

A `Pot` with a `DPDT` stacked on the same shaft (drawn side-by-side with a
dashed "same shaft" link). Forwards `.lug(n)` → pot and `.term(n)` → switch.

The DPDT is drawn `x + 90` to the right of the pot's center; budget that
space in your layout.

---

## `DPDT(x, y, label, throws=2)`

A double-pole double-throw switch. `throws=2` → ON-ON, `throws=3` → ON-OFF-ON.

Terminal layout (2 cols × 3 rows):

```
    [1] [2]    ← throw A (one thrown position connects commons to these)
    [3] [4]    ← commons (the two poles' wipers)
    [5] [6]    ← throw B (the other thrown position)
```

In ON-ON: one position connects `3↔1` and `4↔2`; the other connects `3↔5`
and `4↔6`. In ON-OFF-ON: the middle position leaves both poles open.

`.term(n)` returns the solder point for terminal `n` (1..6).

---

## `SingleCoil(x, y, label, poles=4, hot_color=None, gnd_color=None)`

Vertical rectangle with `poles` pole-piece dots along the centerline.
Defaults to 4 poles (Jazz Bass / P-Bass); pass `poles=6` for Strat-style.

| attr | meaning |
|---|---|
| `.hot` | pickup hot lead endpoint (left, defaults to Fender white) |
| `.gnd` | pickup ground lead endpoint (right, defaults to black) |

Override colors per-pickup: `SingleCoil(..., hot_color="#d00", gnd_color="#000")`.

---

## `Humbucker(x, y, label, leads=2, hot_color=None, gnd_color=None)`

Horizontal rectangle with two rows of 6 pole pieces. Two-conductor or
four-conductor (splittable).

With `leads=2`, the hot and ground lead colors can be customized (default:
black hot, green ground — matching the Seymour Duncan south-finish color
when a 4-conductor pickup is wired as 2-conductor by joining the series
link). Useful for DiMarzio-pink or EMG-colored diagrams.

`leads=2`:

| attr | meaning |
|---|---|
| `.hot` | hot lead |
| `.gnd` | ground lead |

`leads=4` (Seymour Duncan color code):

| attr | color | typical role in default 2-conductor wiring |
|---|---|---|
| `.north_start`  | black (`SD_NORTH_START`)   | hot (north coil start) |
| `.north_finish` | white (`SD_NORTH_FINISH`)  | series link to south (tied to `.south_start`) |
| `.south_start`  | red (`SD_SOUTH_START`)     | series link (tied to `.north_finish`) |
| `.south_finish` | green (`SD_SOUTH_FINISH`)  | ground |
| `.bare`         | shield (`SHIELD`)          | always → ground |

For a coil split: connect `.north_finish` + `.south_start` to ground through
a DPDT or push-pull in the split position; in normal (series) position, leave
that junction floating so the coils stay in series.

Accessing a 2-lead attribute on a 4-lead humbucker (or vice-versa) raises
`AttributeError`.

---

## `Jack(x, y, label="Output Jack", kind="TS")`

Output jack. `kind="TS"` = mono; `kind="TRS"` = stereo (exposes `.ring`).

| attr | meaning |
|---|---|
| `.tip`    | TIP lug — the hot-signal output |
| `.sleeve` | SLEEVE lug — ground |
| `.ring`   | RING lug (TRS only) — often used for stereo, battery switching, or killswitch common |

Accessing `.ring` on a TS jack raises `AttributeError`.

---

## `Capacitor(x, y, value="0.047µF", label=None)`

Non-polar capacitor with `.a` and `.b` solder leads. Common values for guitar
tone caps: `0.022µF` (modern Fender), `0.033µF`, `0.047µF` (vintage Fender /
J-Bass), `0.1µF` (PAF humbucker / 50s Gibson).

---

## `Ground(x, y, label="GND")`

The standard three-bar ground symbol. `.point` returns the hook-up coordinate.

**Prefer `GroundRail` for almost every diagram.** Use `Ground` only for a
tiny, single-pot circuit where a rail would look over-engineered.

---

## `GroundRail(y, x_start, x_end, ground_at="left", label="Chassis GND")`

A visible horizontal ground bus — a thick black line across the bottom of
the canvas with the standard ground symbol hanging off one end. Every
ground wire taps into the rail via `rail.tap(x)`:

```python
rail = d.add(GroundRail(y=820, x_start=200, x_end=1240))
d.wire(vol_n.casing, rail.tap(vol_n.casing[0]),
       color=WireColor.GROUND, route="orth-v")
d.wire(jack.sleeve, rail.tap(jack.sleeve[0]),
       color=WireColor.GROUND, route="orth-v")
```

`rail.tap(x)` returns `(x, rail.y)` clamped to the rail's extent. Typically
`rail.tap(source_x)` so the wire is a straight vertical drop.

Why prefer this over `Ground`: a single star-point node forces every ground
wire to fan in to one `(x, y)`, which reads as clutter. A rail reads as
"this horizontal line IS the ground bus; tap it wherever is convenient."

---

## `ThreeWay(x, y, label="3-Way Toggle")`

Gibson-style pickup-selector toggle. Four solder tabs:

| attr | meaning |
|---|---|
| `.neck`   | wire the neck-pickup signal in here |
| `.bridge` | wire the bridge-pickup signal in here |
| `.common` | selected pickup(s) exit here |
| `.gnd`    | switch-body ground tab |

---

## `FiveWay(x, y, label="5-Way Blade")`

Fender-style 5-way blade selector. Two poles, each with 1 common + 4 throws.

| attr | meaning |
|---|---|
| `.a(1..4)` | pole-A throws |
| `.b(1..4)` | pole-B throws |
| `.a_common` | pole-A wiper |
| `.b_common` | pole-B wiper |
| `.gnd` | switch-body ground tab (above the body) |

Standard Strat wiring uses pole A for the signal path (pickups → common →
output); pole B is free for push-pull / "7-sound" / auto-split mods. Blade
positions (1 = toward-neck, 5 = toward-bridge) short throws together as:

```
pos 1: a1        only
pos 2: a1 + a2   combined
pos 3: a2        only
pos 4: a2 + a3   combined
pos 5: a3        only
```

(Throw `a4` / `b4` is physically present on most switches but rarely used in
stock wiring — it's there for you.)
