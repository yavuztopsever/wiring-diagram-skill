# Common guitar / bass wiring recipes

Each recipe is a **node-to-node netlist**. Translate into
`Diagram.wire(from, to, color=...)` calls using the solder-point attributes
on each component. Unless noted, all pot **casings** go to the ground bus.

Where a lug is listed as **unused**, leave it unwired — don't tie it to
anything. Tying unused lugs to ground can short signal in some circuits.

All pot values are A-taper (audio) unless otherwise specified.

---

## Fender Jazz Bass — V / V / T (stock)

Two single-coils, each with its own volume pot and a shared master tone.

```
Neck.hot    → Vol-N.lug(3)
Neck.gnd    → GND
Bridge.hot  → Vol-B.lug(3)
Bridge.gnd  → GND

Vol-N.lug(1) → GND
Vol-N.lug(2) → output bus junction

Vol-B.lug(1) → GND
Vol-B.lug(2) → output bus junction

output bus  → Tone.lug(2)      # wiper = signal
Tone.lug(1) → Cap.a
Cap.b       → GND
Tone.lug(3) → unused

output bus  → Jack.tip
Jack.sleeve → GND
```

Pots: 250kA × 3. Cap: 0.047µF.

*See `scripts/examples/jazz_bass_series_parallel_dpdt.py` for this recipe
extended with a DPDT series/parallel mod and a DPDT kill switch.*

---

## Fender Precision Bass — V / T (stock)

Split-coil P pickup (wired internally in humbucking series), 1 volume, 1 tone.

```
P-pickup.hot  → Vol.lug(3)
P-pickup.gnd  → GND

Vol.lug(1)    → GND
Vol.lug(2)    → Tone.lug(2)     # and → Jack.tip (junction)

Tone.lug(1)   → Cap.a
Cap.b         → GND
Tone.lug(3)   → unused

Vol.lug(2)    → Jack.tip       # junction with Tone.lug(2)
Jack.sleeve   → GND
```

Pots: 250kA × 2. Cap: 0.047µF (some builds use 0.1µF for vintage warmth).

---

## Fender Stratocaster — 5-way, 1 V + 2 T (stock)

Three single-coils, 5-way blade, master volume, neck tone, middle tone
(bridge pickup has NO tone by default — this is intentional; install a
mod if you want tone on bridge).

```
Neck.hot       → Blade.a(1)
Middle.hot     → Blade.a(2)
Bridge.hot     → Blade.a(3)
Neck.gnd       → GND
Middle.gnd     → GND
Bridge.gnd     → GND

Blade.a_common → Vol.lug(3)

Vol.lug(1)     → GND
Vol.lug(2)     → Jack.tip

# Neck tone on pos 1 & 2 (blade connects Tone-N.lug(2) to Neck via pole B):
Blade.b(1)     → Tone-N.lug(2)
Blade.b(2)     → Tone-N.lug(2)
Tone-N.lug(1)  → Cap-N.a
Cap-N.b        → GND
Tone-N.lug(3)  → unused

# Middle tone on pos 3, 4 (bridge position 5 has no tone):
Blade.b(3)     → Tone-M.lug(2)
Blade.b(4)     → Tone-M.lug(2)
Tone-M.lug(1)  → Cap-M.a
Cap-M.b        → GND
Tone-M.lug(3)  → unused

Jack.sleeve    → GND
```

Pots: 250kA × 3. Caps: 0.022µF × 2.

**"Neck on all positions" mod**: add a push-pull DPDT that, when pulled, ties
`Blade.a(1)` (neck hot) to the `.a_common` directly, bypassing the blade
selector for the neck coil so the neck pickup stays on in every position.

---

## Gibson Les Paul — "Modern" wiring (1980s+)

Two humbuckers (2-conductor), two volume pots, two tone pots, 3-way toggle.

```
Neck-HB.hot    → Vol-N.lug(3)
Neck-HB.gnd    → GND
Bridge-HB.hot  → Vol-B.lug(3)
Bridge-HB.gnd  → GND

Vol-N.lug(1)   → GND
Vol-N.lug(2)   → Tone-N.lug(2)
Vol-N.lug(2)   → Toggle.neck          # (junction)

Vol-B.lug(1)   → GND
Vol-B.lug(2)   → Tone-B.lug(2)
Vol-B.lug(2)   → Toggle.bridge        # (junction)

Tone-N.lug(1)  → Cap-N.a
Cap-N.b        → GND
Tone-N.lug(3)  → unused

Tone-B.lug(1)  → Cap-B.a
Cap-B.b        → GND
Tone-B.lug(3)  → unused

Toggle.common  → Jack.tip
Toggle.gnd     → GND
Jack.sleeve    → GND
```

Pots: 500kA × 4 (humbucker load). Caps: 0.022µF (modern) or 0.047µF (vintage).

**50s wiring variant**: for each volume pot, the tone pot input moves from
`Vol.lug(2)` (wiper) to `Vol.lug(3)` (the pickup-hot input side). Everything
else identical. 50s wiring gives less treble loss as you roll off volume,
and the tone knob now interacts with the volume knob — a signature "Clapton
woman tone" ingredient.

---

## Gibson Les Paul — Coil-split push-pulls (4-conductor humbuckers)

Same as Modern LP wiring above, but:

- Each humbucker uses 4-conductor leads (`leads=4`).
- `.north_finish` tied to `.south_start` externally (the series link).
- `.north_start` → (acts as "hot")
- `.south_finish` → GND
- `.bare` → GND (always)

Then **one Volume pot becomes a PushPullPot**. When pulled UP, the push-pull
DPDT shorts the series-link junction to ground:

```
PushPull.term(3) = <series-link junction>   # N-F tied to S-S of that humbucker
PushPull.term(1) = GND
PushPull.term(5) = <unconnected>    # if ON-ON, pick whichever throw is "pulled"
```

In the **down (normal) position**, T3 connects to T5 (unconnected) → the
series link stays floating → both coils in series → full humbucker.
In the **up (pulled) position**, T3 connects to T1 → series link shorted to
ground → the south coil is shunted → only the north coil heard = "split".

Repeat on the other humbucker's volume pot if you want independent splits.

---

## Fender Telecaster — 3-way "modern" (stock)

Two single-coils, 3-way blade, volume, tone. The 3-way is functionally the
same as a Gibson toggle but with three physical positions instead of
"toggle + flip":

```
Neck.hot      → Blade.neck
Bridge.hot    → Blade.bridge
Neck.gnd      → GND
Bridge.gnd    → GND

Blade.common  → Vol.lug(3)
Vol.lug(1)    → GND
Vol.lug(2)    → Tone.lug(2)
Vol.lug(2)    → Jack.tip             # junction

Tone.lug(1)   → Cap.a
Cap.b         → GND
Tone.lug(3)   → unused

Jack.sleeve   → GND
```

Pots: 250kA × 2. Cap: 0.047µF.

**"4-way Tele" mod**: swap the 3-way for a 4-way lever that adds "neck and
bridge in series" as position 4 (between bridge and both-in-parallel). The
series connection replaces the neck pickup's ground with the bridge pickup's
hot — same mechanism as the J-Bass series/parallel DPDT above.

---

## Treble-bleed circuit (add-on to any volume pot)

When you roll back a guitar's volume, the cable + pot + amp-input form a
low-pass filter that robs treble. A treble-bleed circuit is a small cap (±
resistor) across the volume pot's input and wiper that passes high
frequencies unattenuated.

```
Vol.lug(3)   → <TBleed-Cap.a>       # input (pickup side)
Vol.lug(2)   → <TBleed-Cap.b>       # wiper (output side)
```

Typical values:

- **Cap-only** (Fender-style): 1000pF (0.001µF). Slight high-pass bias.
- **Kinman** (cap + resistor in parallel): 1200pF || 130kΩ. Flatter response.
- **Duncan** (cap + resistor in series): 2200pF + 100kΩ. Preserves mids too.

For drawing this, add a `Capacitor` (and optionally a resistor — not provided
by the library yet; draw manually with the `Diagram` methods) alongside the
volume pot and wire between `.lug(3)` and `.lug(2)`.

---

## Notes on the "output bus junction"

The volume-pot wipers joining each other (and feeding the tone + jack) form
an **electrical junction** that doesn't live on any one component. In
diagrams, draw it as a `d.junction(x, y)` dot in the empty space between the
volume pots. Route all wires meeting there through the same `(x, y)`.

Physically, this junction is a tiny solder blob — on a real guitar, it's
often made on the back of one of the volume pots or on a tag strip. The
diagram represents it as a floating node for clarity.
