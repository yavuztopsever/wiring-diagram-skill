# DPDT switch wiring cookbook

A DPDT (double-pole, double-throw) switch has 6 terminals arranged in a 2×3
grid. Viewed from the back:

```
      [1] [2]     throw A
      [3] [4]     commons (poles) — always connected to ONE of the throws
      [5] [6]     throw B
```

- **Pole 1** = terminal 3. Its wiper connects to either 1 (one position) or 5 (the other).
- **Pole 2** = terminal 4. Its wiper connects to either 2 or 6.
- **ON-ON** (`throws=2`): no middle — always in one thrown position.
- **ON-OFF-ON** (`throws=3`): middle position opens both poles (useful for
  "kill switch" momentary toggles).

The two poles move **together**: flipping the switch simultaneously connects
3→1 and 4→2, OR 3→5 and 4→6. Never one without the other.

---

## The four classical passive mods

Each recipe below is a **terminal-level netlist**. Translate straight into
`Diagram.wire(...)` calls.

### 1. Series / Parallel on a two-pickup instrument

Reroutes the two pickups between parallel (standard, their own vol pots) and
series (one long combined coil).

> **For a full 22-wire node-by-node trace of this mod as implemented in
> `scripts/examples/jazz_bass_series_parallel_dpdt.py`, read
> [`series_parallel_audit.md`](series_parallel_audit.md). It explains
> why the switch does NOT "dump signal to ground" despite the diagram's
> rail carrying many always-on chassis grounds.**

```
T1 = GND                       (parallel throw)
T2 = Vol-B lug 3               (parallel throw)
T3 = Neck pickup ground lead   (pole 1 common)
T4 = Bridge pickup hot lead    (pole 2 common)
T5 = <series link>             ──┐
T6 = <series link>             ──┘  jumper T5↔T6 with a short wire
```

- **Parallel position** (commons connect to throw A = terminals 1,2):
  Neck-gnd → GND, Bridge-hot → Vol-B. Standard wiring restored.
- **Series position** (commons connect to throw B = terminals 5,6):
  T5↔T6 jumper ties Neck-gnd to Bridge-hot. The two pickups now form one
  series loop: Neck-hot → (coil) → Neck-gnd = Bridge-hot → (coil) → Bridge-gnd → GND.

Gives a noticeably hotter, mid-forward tone. Jazz Bass, Tele, P-Bass + J-Bridge, HSS Strat etc. all benefit.

### 2. Phase reverse (on a single pickup)

Flips the polarity of one pickup so it fights the other → thin, honky
"out-of-phase" tone. Uses both poles to swap hot and ground of one pickup.

```
T1 = GND                      (normal)
T2 = Signal out               (normal)
T3 = Pickup ground lead       (pole 1 common)
T4 = Pickup hot lead          (pole 2 common)
T5 = Signal out               (inverted — swapped with T1)
T6 = GND                      (inverted — swapped with T2)
```

- **Normal position**: pickup-gnd → GND, pickup-hot → Signal.
- **Inverted position**: pickup-gnd → Signal, pickup-hot → GND. Polarity flipped.

### 3. Coil split on a 4-conductor humbucker

Shunts one coil to ground, leaving only the other coil in circuit → single-coil-style tone from a humbucker.

```
T1 = <unconnected>            (in split throw)
T2 = <unconnected>
T3 = North-finish lead        (pole 1 common)   — series link with S-S normally
T4 = South-start lead         (pole 2 common)   — series link with N-F normally
T5 = GND                      (split throw)
T6 = GND                      (split throw)
```

- **Normal (series/humbucking) position** (commons → T1, T2 / open):
  N-F and S-S stay joined via their short external wire (the classic series
  link), both coils in series.
- **Split position** (commons → T5, T6 / GND):
  N-F and S-S are shorted to ground. Only one coil (typically the slug coil,
  depending on your north_start→hot wiring) remains in circuit.

Only **one pole is strictly required** — many real splits use SPDT or half a
DPDT (e.g. on a push-pull). The DPDT version above is belt-and-braces:
grounds BOTH mid-points so the split is identical regardless of how the
humbucker is wired into the rest of the circuit.

### 4. Kill switch (stutter / silence)

Interrupts the hot signal AND shorts the jack tip to ground for absolute
silence. Uses both poles to do both jobs in one switch action.

```
T1 = Jack tip                (normal throw)
T2 = <unconnected>           (normal throw — no short in normal)
T3 = Signal coming in        (pole 1 common, from tone pot / output bus)
T4 = Jack tip                (pole 2 common — yes, same node as T1)
T5 = <unconnected>           (kill throw — signal dies here)
T6 = GND                     (kill throw — tip shorted to ground)
```

- **Normal position** (commons → T1, T2): signal T3→T1→Jack tip. T4→T2 is
  open, no short on the tip.
- **Kill position** (commons → T5, T6): signal T3→T5 (dead-ends, nothing
  connected), AND Jack tip T4→T6→GND (tip shorted to ground → silence and
  also drains any charge so there's no "pop").

For a true stutter effect, use a **momentary ON-OFF-ON** DPDT (throws=3),
center-sprung. Press = kill, release = return to normal.

---

## Common pitfalls

- **Don't mix up commons (3/4) with throws.** Commons are always the
  "source" terminals that the switch routes to one of two destinations.
  Wiring a signal source to a throw terminal instead of the common breaks the
  whole mod.
- **Poles move together.** You can't use pole 1 for one mod and pole 2 for
  an unrelated mod on the same switch. Either use one DPDT per mod, or
  choose mods that naturally use both poles (the above four all do).
- **The external T5↔T6 jumper** in the series/parallel mod is essential.
  Without it, the two commons have nowhere to meet in the series position.
- **Never leave an unused common floating** if you can help it — tie it to
  ground or use a 1MΩ resistor to ground to avoid stray noise. In the kill
  circuit above, T4 is always at Jack-tip potential, which is safe.

---

## Industry numbering vs manufacturer numbering

The 1-through-6 numbering here matches Seymour Duncan and most StewMac
diagrams. Some Switchcraft / Carling switches label lugs differently (A/B/C
with a number for the pole). When wiring a real switch, always **confirm
with a continuity test**: in one position, there should be continuity between
commons and throw A; flip the switch, continuity moves to throw B.
