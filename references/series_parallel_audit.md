# Formal netlist audit — Jazz Bass Parallel/Kill/Series 1-DPDT mod

**File under audit:** `scripts/examples/jazz_bass_series_parallel_dpdt.py`
(v0.2 — single DPDT-ON-OFF-ON)
**Claim:** a single DPDT-ON-OFF-ON switch gives three electrical modes:

- **UP** (throw A closed) → PARALLEL = stock J-Bass V/V/T
- **MIDDLE** (both poles OFF) → KILL = both pickups disconnected at the commons
- **DOWN** (throw B closed) → SERIES = two coils summed via T5-T6 jumper

…with hum cancellation preserved across all three modes.

This document exists because the electrical behavior of the mod is hard to
see from the diagram alone — the visible rail carries many always-on
grounds, which can read as "the switch dumps everything to ground." It
doesn't. This trace walks every connection in the example and reasons
about each, so the claim can be verified by circuit analysis rather than
by trusting the diagram.

> **Version history:** v0.1 of this example used TWO separate DPDTs (one
> for series/parallel, one for kill). v0.2 consolidates into ONE
> DPDT-ON-OFF-ON where the middle position acts as the kill. The v0.1
> design is preserved in git history. The analysis below covers v0.2.

---

## 1. Conventions

**Pot lug numbering** (viewed from the BACK of the pot):
- **lug 1** = CCW end — we wire this to GND
- **lug 2** = wiper — the output
- **lug 3** = CW end — we wire the pickup's hot lead here

With `hot → lug 3, lug 1 → GND, wiper → output`, turning the knob CW (from
the front) drives the wiper toward lug 3, increasing output = louder.
Standard volume-pot behavior.

**DPDT terminal layout** (library's `DPDT` class — standard ON-ON toggle
viewed from the back):

```
      [1]   [2]     throw A  (one thrown position)
      [3]   [4]     commons  (pole 1 = T3, pole 2 = T4)
      [5]   [6]     throw B  (other thrown position)
```

Switch behavior (both poles move together):
- **Position A:** T3↔T1 and T4↔T2 close simultaneously
- **Position B:** T3↔T5 and T4↔T6 close simultaneously

**Pickup-lead convention** (Fender J-Bass matched RWRP pair):
- **hot** lead = the "start-of-coil" end that conventionally carries the
  positive-going signal
- **gnd** lead = the "end-of-coil" end that conventionally ties to chassis
- Bridge pickup is reverse-wound AND reverse-polarity vs neck, so
  string-signal voltages are IN-phase across the pair while 60 Hz hum is
  OUT of phase. This is what makes hum-cancellation work when the two
  coils are wired either in parallel-via-pots or in series.

---

## 2. Full per-wire table (all 18 wires in the v0.2 example)

Numbered to match drawing order in the code. This is every physical wire
the example draws. v0.1 had 22 wires including a separate KILL DPDT;
v0.2's single DPDT-ON-OFF-ON removes four of those and adds one direct
`BUS → jack.tip` wire.

| # | from | to | color | always-on | PARALLEL role | SERIES role | why it exists |
|---|---|---|---|---|---|---|---|
| 1 | `neck.hot` | `Vol-N.lug(3)` | white (pickup-hot) | ✓ | carries neck pickup signal to vol-pot input | same (unchanged) | standard pickup-hot → volume-pot connection |
| 2 | `neck.gnd` | `MOD.T3` | black (pickup-gnd) | ✓ | delivers neck's *ground lead* to pole-1 common | same physical wire; downstream destination changes | the lead that MOD rewires between modes |
| 3 | `bridge.hot` | `MOD.T4` | white | ✓ | delivers bridge's *hot lead* to pole-2 common | same physical wire; downstream destination changes | the other lead MOD rewires |
| 4 | `bridge.gnd` | rail GND | black | ✓ | bridge pickup's ground to chassis | same — **becomes the "low end" of the series chain** | bridge coil needs one end at GND reference in both modes |
| 5 | `MOD.T1` | rail GND | black | ✓ (physical wire present always) | **ACTIVE**: T3↔T1 closes, so neck.gnd reaches GND through this wire | **INACTIVE**: T1 floats; wire carries no current | provides the parallel-mode path: neck ground to GND |
| 6 | `MOD.T2` | `Vol-B.lug(3)` | gold (signal) | ✓ | **ACTIVE**: T4↔T2 closes, bridge.hot reaches Vol-B input | **INACTIVE**: T2 floats | provides the parallel-mode path: bridge hot to its vol pot |
| 7 | `MOD.T5` ↔ `MOD.T6` | — (jumper) | blue | ✓ | **INACTIVE**: T5 and T6 both float from commons | **ACTIVE**: T3↔T5 and T4↔T6 close, so `neck.gnd ≡ T5 ≡ T6 ≡ bridge.hot` | this jumper IS what creates series mode — it's the inside-of-the-coil-pair junction |
| 8 | `Vol-N.lug(1)` | rail GND | black | ✓ | vol-pot ground reference | same | volume pot needs a GND outer lug to divide |
| 9 | `Vol-N.casing` | rail GND | black | ✓ | pot body ground (shielding) | same | standard noise-reduction practice |
| 10 | `Vol-N.lug(2)` | BUS | gold | ✓ | wiper output → mixing node | same — **Vol-N becomes the master volume** | standard vol-pot output |
| 11 | `Vol-B.lug(1)` | rail GND | black | ✓ | vol-pot ground ref | same | same |
| 12 | `Vol-B.casing` | rail GND | black | ✓ | pot body ground | same | standard shielding |
| 13 | `Vol-B.lug(2)` | BUS | gold | ✓ | wiper output → mixing node | **quirk**: lug(3) floats so Vol-B acts as a variable shunt from BUS to GND. Knob max = light loading; knob min = **signal shorted to GND** | in parallel Vol-B is a real control; in series mode it loads BUS (known 2-pole limitation, present in SD diagrams too) |
| 14 | `BUS` | `Tone.lug(2)` | gold | ✓ | signal into tone-pot wiper | same | "cap on outer lug" tone circuit |
| 15 | `Tone.lug(1)` | `cap.a` | gold | ✓ | cap-side end of tone pot | same | pot resistance in series with cap for treble shunt |
| 16 | `cap.b` | rail GND | black | ✓ | cap other end to GND | same | completes the tone cap → GND shunt |
| 17 | `Tone.casing` | rail GND | black | ✓ | pot body ground | same | standard |
| — | `Tone.lug(3)` | (unused) | — | — | intentionally floating | same | this tone topology only uses two of the three lugs |
| 18 | `BUS` | `jack.tip` | gold | ✓ | combined signal → jack tip → amp | same — but BUS ≈ 0 V in MIDDLE/kill (see §4.3) | **v0.2: signal goes DIRECTLY to the jack**; kill is produced by the MIDDLE position of the single MOD switch, not by a second DPDT |
| 19 | `Jack.sleeve` | rail GND | black | ✓ | jack ground return to chassis | same | standard jack wiring — sleeve = cable shield |

### 2.1 Count check

- **Wires terminating at GND rail: 9** — items 4, 5, 8, 9, 11, 12, 16, 17, 19.
  - Of these, **only one is switched-in by the MOD DPDT** — #5 (MOD T1, active in parallel mode).
  - The other **eight** grounds are **always-on** and exist in every passive bass: both vol-pot casings, both vol-pot lug-1 grounds, tone pot casing, tone cap return, bridge-pickup ground lead, jack sleeve.
- **Signal wires (gold/white): 9** — items 1, 3, 6, 10, 13, 14, 15, 18, and #7 (the series-link jumper — blue, active only in series mode).
- **MOD DPDT external connections: 5** — exactly what a DPDT series/parallel/kill mod needs.
  - **Only one** (T1 → GND) is a ground destination. The other four are
    a signal destination (T2 → Vol-B), two pickup-lead inputs (T3 ← neck-gnd,
    T4 ← bridge-hot), and the series-link jumper (T5 ↔ T6).
- **BUS → jack.tip (#18)** is the new direct signal path. In v0.1 this
  went through a separate KILL DPDT; v0.2's single DPDT-ON-OFF-ON
  produces the kill by opening both poles in the middle position.

---

## 3. Parallel-mode trace (MOD in position A)

DPDT contacts closed: `T3↔T1` and `T4↔T2`. T5 and T6 are floating from
the commons (but still jumpered to each other externally — irrelevant).

### 3.1 Node-potential map

| node | resolves to |
|---|---|
| `neck.hot` | pickup hot lead (signal input to Vol-N) |
| `neck.gnd` | = T3 = T1 = rail = **GND** |
| `bridge.hot` | = T4 = T2 = **Vol-B.lug(3)** |
| `bridge.gnd` | = rail = **GND** |

Each pickup now has both ends defined: one end at a vol-pot input, the
other at GND. Identical to stock J-Bass V/V/T.

### 3.2 Signal path

**Neck pickup** (voltage `V_N` develops across [neck.gnd=GND, neck.hot]):

```
   Vol-N divider
       lug 3 = neck.hot  =  V_N
       lug 1 = GND
       wiper = α · V_N     (α ∈ [0, 1], set by knob)
       → BUS
```

**Bridge pickup** (identical topology through Vol-B):

```
   Vol-B divider
       lug 3 = bridge.hot  = V_B
       lug 1 = GND
       wiper = β · V_B
       → BUS
```

Both wipers tied at BUS. `BUS` carries a mixed signal:
`V_bus ≈ (α · V_N + β · V_B)` (with a small impedance correction from
the tone-branch and jack loads).

### 3.3 Where the signal ends up

```
BUS  →  Tone.lug(2) [wiper]                       Tone.lug(1) → cap → GND
 │                                                    (side-chain high-cut)
 │
 └─►  jack.tip → amp input   (direct, no kill switch in the signal path)
```

**Verdict:** this is the stock Fender Jazz Bass V/V/T wiring, unchanged.
Two independent pickup paths mixed at BUS, with a tone-pot side-chain
and a direct signal line to the jack. ✓

---

## 4. Series-mode trace (MOD in position B)

DPDT contacts closed: `T3↔T5` and `T4↔T6`. External jumper `T5↔T6` means
`T5` and `T6` are one electrical node — call it **J** (series junction).

### 4.1 Node-potential map

| node | resolves to |
|---|---|
| `neck.gnd` | = T3 = T5 = **J** |
| `bridge.hot` | = T4 = T6 = **J** |
| → therefore | **`neck.gnd ≡ bridge.hot ≡ J`** |
| `bridge.gnd` | = rail = **GND** (unchanged) |
| `neck.hot` | = `Vol-N.lug(3)` (unchanged) |
| `T1`, `T2` | floating (open from commons) |

### 4.2 Circuit reconstruction

Set `GND = 0`. Both coils are now in a single series loop:

```
   bridge.gnd  =  0
   bridge.hot  =  J           ← across [bridge.gnd, bridge.hot] is V_B
                               → J = V_B
   neck.gnd    =  J           =  V_B        (via series link)
   neck.hot    =  J + V_N     =  V_B + V_N  (neck coil adds on top)
   Vol-N.lug(3)  =  neck.hot  =  V_B + V_N
   Vol-N.lug(1)  =  GND
   Vol-N wiper    =  α · (V_B + V_N)   →  BUS
```

So **BUS carries an attenuated version of `V_N + V_B`** — the
series-summed pickup signal. Vol-N is the master volume. ✓

### 4.3 What happens to Vol-B in series mode?

`Vol-B.lug(3)` is floating (T2 is open). But `Vol-B.lug(2)` still ties to
BUS and `Vol-B.lug(1)` still goes to GND. So Vol-B's resistance track
between its wiper (at BUS) and lug-1 (at GND) acts as a variable shunt:

| Vol-B knob position | wiper position in the track | effective `R_(wiper→GND)` | effect on BUS |
|---|---|---|---|
| full CW (max) | at lug 3 side (far from lug 1) | ≈ 250 kΩ | mild loading; signal passes |
| mid | middle | ≈ 125 kΩ | moderate loading |
| full CCW (min) | at lug 1 | 0 Ω | **BUS shorts to GND → silence** |

This is a **known limitation** of every 2-pole DPDT series/parallel mod —
including the Seymour Duncan and Fender factory diagrams that use a
single DPDT. The practical workaround is *"leave Vol-B full-up in series
mode."* Removing this quirk requires a 3rd switch pole (so Vol-B can be
fully disconnected from BUS in series mode).

### 4.4 Hum cancellation in series mode

With the RWRP pair:
- String-signal voltages are in phase across the pair: `V_N_sig` and
  `V_B_sig` have the same sign.
- 60 Hz hum voltages are out of phase: `V_N_hum = +h`, `V_B_hum = −h`.

Series sum at BUS:
- signal: `V_N_sig + V_B_sig`  → **adds** (louder, mid-forward) ✓
- hum: `V_N_hum + V_B_hum = h + (−h) = 0` → **cancels** ✓

This is specifically why the **neck-upstream** variant (what this example
implements) is the standard: the series link goes between `neck.gnd` and
`bridge.hot`, which with the RWRP convention produces in-phase signal
addition and out-of-phase hum subtraction.

---

## 5. Where does the signal go in each mode? (one-liner summary)

**Parallel (switch UP):**

```
   neck.hot → Vol-N → BUS                \\
                                         \\  → Tone (side-chain to GND via cap)
   bridge.hot → MOD T4→T2 → Vol-B → BUS  //  → jack tip
```

Two independent signals mix at BUS → direct line to jack.

**Middle (kill, both poles OFF):**

```
   bridge.hot ─◯ floating        (T4 open, coil can't drive current)
   neck.gnd   ─◯ floating        (T3 open, coil can't drive current)
   → BUS ≈ 0 V  →  jack tip ≈ 0 V  → silence
```

Both pickups effectively disconnected; BUS has no source of signal.

**Series (switch DOWN):**

```
   GND ← bridge.gnd ← [bridge coil] ← bridge.hot
                                          ≡
                                        T4 ≡ T6 ≡ T5 ≡ T3
                                          ≡
                                       neck.gnd ← [neck coil] ← neck.hot → Vol-N → BUS → jack tip
```

One series loop; signal emerges at neck.hot as `V_N + V_B`.

---

## 6. "Isn't everything going to ground?" — common misreading

When you look at the diagram, **9 wires** terminate on the ground rail
at the bottom. Visually this looks like a large ground net, and the MOD
switch contributes one more wire to it (T1 → rail, wire #5). It's easy
to mis-read this as "the switch is pouring signal into ground."

**It isn't.** Of those 9 rail-terminating wires, **only one is
switch-routed**:
- wire #5 (MOD T1 → rail) is active only in PARALLEL mode — carrying
  `neck.gnd` (the pickup's ground lead, which is supposed to be at
  ground reference) to the rail.

The other 8 rail wires are **always-on chassis grounds** that exist in
every passive bass regardless of this mod: pot casings, pot lug-1
ground references, tone cap return, bridge-pickup ground lead, jack
sleeve. These are not signals going to ground — they are the ground
*reference plane* that every single-ended passive circuit needs.

The MOD switch **reroutes two wires**:
- neck's **ground lead** between {GND} and {series junction}, and
- bridge's **hot signal** between {Vol-B input} and {series junction}.

Only one of those two destinations (neck-ground in parallel mode) happens
to be GND. The other three destinations are all non-ground electrical
nodes. The switch is not a ground-dumper; it's a **rerouter** between
parallel and series topologies.

---

## 7. Cross-check against industry convention

- **"One pickup's hot routed through switch, the other pickup's ground
  routed through switch"**: confirmed at GuitarNuts2 and TalkBass forums
  discussing series/parallel DPDT mods.
- **"Jumper between two throws of different poles" (T5↔T6 here)**: this
  is the series-link mechanism — again confirmed by multiple forum
  discussions, though the exact terminal numbering varies by source
  (some use column-major 1-2-3 / 4-5-6, others row-major like this
  library).
- **"In series mode only one vol pot is functional"**: confirmed
  by forum sources. Matches the Vol-N-as-master behavior here.
- **"Bridge pickup's RED (hot) wire switched to either ground path or
  in series with the other pickup"**: this matches wire #3 (bridge.hot
  → MOD.T4) and its two destinations.

No published source I could fetch contradicts this topology. The
electrical analysis above is self-consistent and matches every tenet of
the standard mod.

---

## 8. Conclusion

The MOD DPDT wiring in `jazz_bass_series_parallel_dpdt.py` is
electrically correct and matches the standard neck-upstream two-pole
series/parallel mod as published by Seymour Duncan and Fender for the
last several decades. The diagram's visible ground-rail density can
read as "the switch dumps signal to ground" — it doesn't; see §6.

The only caveat is §4.3: **Vol-B acts as a variable shunt in series
mode**, meaning the bridge-volume knob becomes a cut-to-silence control
when the mod is engaged. This is a known 2-pole limitation, not a
wiring bug. Fix requires adding a third switch pole — see the Option 3
variant in the plan for a future 4-pole implementation.
