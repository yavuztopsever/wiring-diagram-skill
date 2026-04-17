"""Guitar / bass wiring diagram library.

Produces electronically accurate SVG diagrams in the top-down Seymour-Duncan /
StewMac style. Every component exposes real solder-point coordinates so wires
attach to actual terminals, not arbitrary points.

Coordinate system: SVG user units, origin top-left, y grows DOWN.

Terminal numbering conventions (critical for accuracy):

  Pot (viewed from back, shaft toward viewer):
      lug 1 = CCW end, lug 2 = wiper, lug 3 = CW end.

  DPDT (viewed from back, lever up):
      [1] [2]    throw A  (connects to commons in one position)
      [3] [4]    commons  (the two poles' wipers)
      [5] [6]    throw B  (connects to commons in the other position)

  Jack (TS / TRS): .tip, .sleeve (, .ring for TRS).

  Pickup leads: .hot, .gnd for 2-conductor; 4-conductor humbuckers expose
      .north_start, .north_finish, .south_start, .south_finish, .bare
      (Seymour Duncan colors: N-S=black, N-F=white, S-S=red, S-F=green).
"""

from __future__ import annotations

import math
from pathlib import Path

import drawsvg as dw


class WireColor:
    """Industry-standard wire colors. Use these constants when drawing wires
    so the diagram reads correctly to anyone working from it."""

    HOT = "#e4a82f"            # signal hot bus (golden)
    GROUND = "#1a1a1a"         # ground
    PICKUP_HOT_WHITE = "#f8f8f8"   # Fender-style pickup hot lead (white)
    PICKUP_GROUND = "#1a1a1a"      # pickup ground lead (black)
    SHIELD = "#999999"             # bare shield
    # Seymour Duncan 4-conductor humbucker
    SD_NORTH_START = "#1a1a1a"     # black
    SD_NORTH_FINISH = "#f8f8f8"    # white
    SD_SOUTH_START = "#d32222"     # red
    SD_SOUTH_FINISH = "#1d8a2f"    # green


def _point(p):
    """Accept (x,y) tuple or object with .x/.y. Return (x,y)."""
    if hasattr(p, "x") and hasattr(p, "y") and not hasattr(p, "__len__"):
        return (p.x, p.y)
    return tuple(p)


class Component:
    """Base class. Subclasses set position, store solder points, implement draw().

    Every subclass must also implement `bbox(margin=0)` returning a keep-out
    rectangle as `(x1, y1, x2, y2)`. The Diagram uses these to detect wires
    that would pass through a component body, and to let layouts route around
    components via `route_around()`.
    """

    def __init__(self, x: float, y: float, label: str):
        self.x = float(x)
        self.y = float(y)
        self.label = label

    def draw(self, svg: dw.Drawing) -> None:
        raise NotImplementedError

    def bbox(self, margin: float = 0) -> tuple[float, float, float, float]:
        """Keep-out rectangle around the visible body (not the leads).
        Subclasses override with a real rect."""
        return (self.x - margin, self.y - margin,
                self.x + margin, self.y + margin)


def _segment_hits_bbox(x1, y1, x2, y2, bbox) -> bool:
    """True if the line segment (x1,y1)-(x2,y2) intersects `bbox` interior.
    Uses Liang-Barsky clipping; sufficient for axis-aligned obstacles."""
    bx1, by1, bx2, by2 = bbox
    dx, dy = x2 - x1, y2 - y1
    p = (-dx, dx, -dy, dy)
    q = (x1 - bx1, bx2 - x1, y1 - by1, by2 - y1)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if pi == 0:
            if qi < 0:
                return False
        else:
            t = qi / pi
            if pi < 0:
                if t > u2: return False
                if t > u1: u1 = t
            else:
                if t < u1: return False
                if t < u2: u2 = t
    return u1 < u2


def _path_hits_any(points, bboxes) -> bool:
    """True if any segment of the poly-line hits any bbox."""
    pts = [_point(p) for p in points]
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        for bb in bboxes:
            if _segment_hits_bbox(x1, y1, x2, y2, bb):
                return True
    return False


def route_around(p_from, p_to, obstacles,
                 clearance: float = 12,
                 prefer: str = "orth") -> list[tuple[float, float]]:
    """Return a list of waypoints from `p_from` to `p_to` that avoid every
    bbox in `obstacles`. `clearance` is how far outside an obstacle the
    detour should go.

    Starts with simple L-routes; if they hit obstacles, inserts a detour
    around the blocking obstacle. Good enough for single-obstacle detours;
    for complex cases, pass explicit waypoints to `wire_path()`.
    """
    x1, y1 = _point(p_from)
    x2, y2 = _point(p_to)

    candidates = []
    if prefer == "orth":
        candidates += [[(x1, y1), (x2, y1), (x2, y2)],
                       [(x1, y1), (x1, y2), (x2, y2)]]
    else:
        candidates += [[(x1, y1), (x1, y2), (x2, y2)],
                       [(x1, y1), (x2, y1), (x2, y2)]]

    for cand in candidates:
        if not _path_hits_any(cand, obstacles):
            return cand

    # Find the first obstacle blocking a direct L-route; detour around it.
    for bb in obstacles:
        bx1, by1, bx2, by2 = bb
        # Try routing ABOVE the obstacle: go to obstacle_top - clearance,
        # then across, then down to target.
        top_y = by1 - clearance
        for detour in (
            # vertical-first with mid_x chosen to avoid going back through bb
            [(x1, y1), (x1, top_y), (x2, top_y), (x2, y2)],
            # horizontal-first on top
            [(x1, y1), (x1, top_y), (bx1 - clearance, top_y),
             (bx1 - clearance, y2), (x2, y2)],
            [(x1, y1), (x1, top_y), (bx2 + clearance, top_y),
             (bx2 + clearance, y2), (x2, y2)],
            # bottom routes
            [(x1, y1), (x1, by2 + clearance), (x2, by2 + clearance), (x2, y2)],
        ):
            if not _path_hits_any(detour, obstacles):
                return detour
    # Last resort — direct line, caller can still draw it but know it's ugly.
    return [(x1, y1), (x2, y2)]


class Diagram:
    """SVG canvas. Add components, draw wires between their solder points, save."""

    def __init__(self, width: int = 1100, height: int = 820,
                 title: str | None = None, subtitle: str | None = None):
        self.width = width
        self.height = height
        self.title = title
        self.subtitle = subtitle
        self._svg = dw.Drawing(width, height, origin=(0, 0))
        # white background
        self._svg.append(dw.Rectangle(0, 0, width, height, fill="#ffffff"))
        if title:
            self._svg.append(dw.Text(
                title, 20, width / 2, 32,
                text_anchor="middle", font_family="sans-serif",
                font_weight="bold", fill="#111",
            ))
        if subtitle:
            self._svg.append(dw.Text(
                subtitle, 12, width / 2, 54,
                text_anchor="middle", font_family="sans-serif",
                fill="#555",
            ))
        self._components: list[Component] = []
        self._wire_endpoints: list[tuple[float, float]] = []
        self._obstacles: list[tuple[float, float, float, float]] = []

    def add(self, component: Component) -> Component:
        component.draw(self._svg)
        self._components.append(component)
        bb = component.bbox()
        # A zero-area bbox means the subclass didn't override; skip it.
        if bb[2] > bb[0] and bb[3] > bb[1]:
            self._obstacles.append(bb)
        return component

    def obstacles(self, exclude: list | None = None) -> list:
        """Return the current obstacle list, optionally excluding specific
        components (pass their `.bbox()` or the component itself)."""
        exc = []
        for e in (exclude or []):
            if isinstance(e, Component):
                exc.append(e.bbox())
            else:
                exc.append(tuple(e))
        return [o for o in self._obstacles if o not in exc]

    def wire(self, p_from, p_to, color: str = "#1a1a1a",
             width: float = 2.2, route: str = "orth",
             label: str | None = None,
             mid_y: float | None = None, mid_x: float | None = None,
             warn_on_hit: bool = True) -> list[tuple[float, float]]:
        """Draw a wire between two solder points. Returns the waypoint list.

        route:
          "direct" – straight line
          "orth"   – L-shape: horizontal first then vertical
          "orth-v" – L-shape: vertical first then horizontal
          "z"      – Z-shape: vertical, horizontal, vertical
                     (default mid_y = midpoint; override with `mid_y=...`)
          "z-h"    – Z-shape: horizontal, vertical, horizontal
                     (default mid_x = midpoint; override with `mid_x=...`)

        When `warn_on_hit=True` and a registered obstacle lies on the drawn
        path, a warning is printed with the offending segment. Use
        `wire_path()` for manual waypoint control when this happens.
        """
        x1, y1 = _point(p_from)
        x2, y2 = _point(p_to)

        if route == "direct":
            pts = [(x1, y1), (x2, y2)]
        elif route == "orth":
            pts = [(x1, y1), (x2, y1), (x2, y2)]
        elif route == "orth-v":
            pts = [(x1, y1), (x1, y2), (x2, y2)]
        elif route == "z":
            my = mid_y if mid_y is not None else (y1 + y2) / 2
            pts = [(x1, y1), (x1, my), (x2, my), (x2, y2)]
        elif route == "z-h":
            mx = mid_x if mid_x is not None else (x1 + x2) / 2
            pts = [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]
        else:
            raise ValueError(f"unknown route: {route!r}")

        return self.wire_path(pts, color=color, width=width, label=label,
                              warn_on_hit=warn_on_hit)

    def wire_path(self, points, color: str = "#1a1a1a",
                  width: float = 2.2, label: str | None = None,
                  warn_on_hit: bool = True) -> list[tuple[float, float]]:
        """Draw a wire through a sequence of explicit waypoints.

        Prefer this over `wire()` whenever an orthogonal L or Z route would
        cut through a component body. You can hand-pick waypoints, or
        compute them with the module-level `route_around()` helper.
        """
        if len(points) < 2:
            raise ValueError("wire_path needs at least 2 points")
        pts = [_point(p) for p in points]

        # Collision check against registered obstacles. A segment is OK if
        # either endpoint is on/inside the obstacle (wire is attaching to
        # that component, or running alongside from a terminal).  Only flag
        # segments that PASS THROUGH an obstacle with BOTH endpoints outside.
        if warn_on_hit:
            eps = 3
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                for bb in self._obstacles:
                    bx1, by1, bx2, by2 = bb
                    # endpoint-in-bbox test (with small epsilon for boundary)
                    def _in(x, y):
                        return (bx1 - eps <= x <= bx2 + eps and
                                by1 - eps <= y <= by2 + eps)
                    if _in(x1, y1) or _in(x2, y2):
                        continue
                    # shrink bbox slightly so grazing the edge isn't a hit
                    shrunk = (bx1 + eps, by1 + eps,
                              bx2 - eps, by2 - eps)
                    if shrunk[2] <= shrunk[0] or shrunk[3] <= shrunk[1]:
                        continue
                    if _segment_hits_bbox(x1, y1, x2, y2, shrunk):
                        import sys
                        sys.stderr.write(
                            f"[wiring] WARNING: wire segment "
                            f"({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f}) "
                            f"passes through obstacle bbox {bb}. "
                            f"Consider a manual wire_path() detour.\n"
                        )

        if _is_light(color):
            # Darker, fully-opaque outline so white pickup wires are clearly
            # visible on the white canvas. Reads as "white wire with a
            # defined edge" — standard schematic convention for insulated
            # wire that happens to be white.
            outline = dw.Path(
                stroke="#2a2a2a", stroke_width=width + 1.8, fill="none",
                stroke_linecap="round", stroke_linejoin="round",
            )
            outline.M(*pts[0])
            for p in pts[1:]:
                outline.L(*p)
            self._svg.append(outline)

        path = dw.Path(
            stroke=color, stroke_width=width, fill="none",
            stroke_linecap="round", stroke_linejoin="round",
        )
        path.M(*pts[0])
        for p in pts[1:]:
            path.L(*p)
        self._svg.append(path)

        # solder dots at endpoints only (no dots at interior waypoints).
        # Kept small (1.8) so they sit INSIDE the component's own terminal
        # circle without dominating it — avoids the "bubble on top of a
        # bubble" look at switch terminals.
        self._svg.append(dw.Circle(*pts[0], 1.8, fill=color))
        self._svg.append(dw.Circle(*pts[-1], 1.8, fill=color))
        self._wire_endpoints.extend([pts[0], pts[-1]])

        if label:
            # place label on the LONGEST segment, offset perpendicularly
            longest = 0.0
            mid = None
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                dx, dy = x2 - x1, y2 - y1
                length = (dx * dx + dy * dy) ** 0.5
                if length > longest:
                    longest = length
                    mid = ((x1 + x2) / 2, (y1 + y2) / 2, dx, dy)
            if mid and longest > 20:
                lx, ly, dx, dy = mid
                if abs(dx) >= abs(dy):
                    # horizontal segment → label ABOVE, centered
                    self._svg.append(dw.Text(
                        label, 10, lx, ly - 7,
                        text_anchor="middle", font_family="sans-serif",
                        fill="#333", font_style="italic",
                    ))
                else:
                    # vertical segment → label to the RIGHT, centered vertically
                    self._svg.append(dw.Text(
                        label, 10, lx + 10, ly + 3,
                        text_anchor="start", font_family="sans-serif",
                        fill="#333", font_style="italic",
                    ))

        return pts

    def wire_with_hops(self, p_from, p_to, crossings: list,
                        color: str = "#1a1a1a", width: float = 2.2,
                        hop_size: float = 7, hop_side: str | None = None,
                        label: str | None = None) -> list:
        """Draw a STRAIGHT wire from `p_from` to `p_to`, with a small
        semicircle hop-arc at each point in `crossings`. The hopping wire
        is *this* wire — the wire it crosses is expected to be drawn as a
        continuous line UNDER the arc.

        Use whenever a wire would cross another wire of the SAME color (so
        the standard "no junction dot = not connected" convention might be
        misread). Only needs to be used for that specific case; different-
        color crossings can just use `wire()`.

        The wire must be strictly horizontal (y_from == y_to) or strictly
        vertical (x_from == x_to). `hop_side` chooses which way the arc
        bulges: "right"/"left" for vertical wires (default "right"),
        "up"/"down" for horizontal wires (default "up").

        Example
        -------
            # Bridge-ground vertical at x=499 crosses neck-ground horizontal
            # at y=400 — both are black. Hop over it so the crossing reads.
            d.wire_with_hops(
                bridge.gnd, rail.tap(bridge.gnd[0]),
                crossings=[(499, 400)],
                color=WireColor.PICKUP_GROUND,
            )
        """
        x1, y1 = _point(p_from)
        x2, y2 = _point(p_to)

        if x1 == x2:
            orientation = "v"
            side = hop_side or "right"
            if side not in ("right", "left"):
                raise ValueError("hop_side for a vertical wire must be 'right' or 'left'")
        elif y1 == y2:
            orientation = "h"
            side = hop_side or "up"
            if side not in ("up", "down"):
                raise ValueError("hop_side for a horizontal wire must be 'up' or 'down'")
        else:
            raise ValueError("wire_with_hops requires a strictly horizontal or vertical wire")

        # Filter crossings that actually lie on the wire and sort along direction.
        if orientation == "v":
            direction = 1 if y2 > y1 else -1
            valid = [c for c in crossings
                     if abs(c[0] - x1) < 1 and
                        min(y1, y2) < c[1] < max(y1, y2)]
            valid.sort(key=lambda c: c[1] * direction)
        else:
            direction = 1 if x2 > x1 else -1
            valid = [c for c in crossings
                     if abs(c[1] - y1) < 1 and
                        min(x1, x2) < c[0] < max(x1, x2)]
            valid.sort(key=lambda c: c[0] * direction)

        # Build a single path with moves/lines/arcs.
        def build(path):
            path.M(x1, y1)
            cur_x, cur_y = x1, y1
            for cx, cy in valid:
                if orientation == "v":
                    seg_end_y = cy - hop_size * direction
                    path.L(cur_x, seg_end_y)
                    ctrl_x = cur_x + hop_size * 1.3 * (1 if side == "right" else -1)
                    ctrl_y = cy
                    next_y = cy + hop_size * direction
                    path.Q(ctrl_x, ctrl_y, cur_x, next_y)
                    cur_y = next_y
                else:
                    seg_end_x = cx - hop_size * direction
                    path.L(seg_end_x, cur_y)
                    ctrl_y = cur_y + hop_size * 1.3 * (-1 if side == "up" else 1)
                    ctrl_x = cx
                    next_x = cx + hop_size * direction
                    path.Q(ctrl_x, ctrl_y, next_x, cur_y)
                    cur_x = next_x
            path.L(x2, y2)
            return path

        if _is_light(color):
            outline = build(dw.Path(
                stroke="#2a2a2a", stroke_width=width + 1.8, fill="none",
                stroke_linecap="round", stroke_linejoin="round",
            ))
            self._svg.append(outline)

        path = build(dw.Path(
            stroke=color, stroke_width=width, fill="none",
            stroke_linecap="round", stroke_linejoin="round",
        ))
        self._svg.append(path)

        # solder dots at endpoints only
        self._svg.append(dw.Circle(x1, y1, 1.8, fill=color))
        self._svg.append(dw.Circle(x2, y2, 1.8, fill=color))
        self._wire_endpoints.extend([(x1, y1), (x2, y2)])

        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            if orientation == "v":
                self._svg.append(dw.Text(
                    label, 10, mx + 10, my,
                    text_anchor="start", font_family="sans-serif",
                    fill="#333", font_style="italic",
                ))
            else:
                self._svg.append(dw.Text(
                    label, 10, mx, my - 7,
                    text_anchor="middle", font_family="sans-serif",
                    fill="#333", font_style="italic",
                ))

        return [(x1, y1), (x2, y2)]

    def crossover(self, x: float, y: float, orientation: str = "h",
                  size: float = 8) -> None:
        """Draw a wire-crossing hop at (x, y) — a small arc showing that two
        wires cross WITHOUT connecting.

        `orientation="h"` draws a humped-up arc on a horizontal wire (so a
        vertical wire passes under). `orientation="v"` draws a sideways
        hump on a vertical wire.

        Call this BEFORE drawing the hopped-over wire so the arc paints on top.
        """
        if orientation == "h":
            path = dw.Path(
                stroke="#1a1a1a", stroke_width=2.2, fill="#ffffff",
                stroke_linecap="round",
            )
            path.M(x - size, y).Q(x, y - size * 1.5, x + size, y)
            self._svg.append(path)
        elif orientation == "v":
            path = dw.Path(
                stroke="#1a1a1a", stroke_width=2.2, fill="#ffffff",
                stroke_linecap="round",
            )
            path.M(x, y - size).Q(x + size * 1.5, y, x, y + size)
            self._svg.append(path)
        else:
            raise ValueError(f"orientation must be 'h' or 'v', got {orientation!r}")

    def assert_complete(self, strict: bool = False) -> list[str]:
        """Audit the diagram: report any pickup lead or jack terminal that
        has no wire attached. Returns a list of warning strings; also
        raises `RuntimeError` if `strict=True` and problems were found.

        Call this AFTER all wires are drawn but BEFORE save_svg().
        """
        warnings: list[str] = []
        endpoints = {(round(p[0], 1), round(p[1], 1))
                     for p in self._wire_endpoints}

        def check(comp, attr_names, kind):
            for name in attr_names:
                if not hasattr(comp, name):
                    continue
                try:
                    pt = getattr(comp, name)
                    # property that raises on unsupported attribute
                    if callable(pt):
                        continue
                except AttributeError:
                    continue
                key = (round(pt[0], 1), round(pt[1], 1))
                if key not in endpoints:
                    warnings.append(
                        f"{kind} '{comp.label}' has unwired .{name} at "
                        f"({pt[0]:.0f}, {pt[1]:.0f})"
                    )

        for c in self._components:
            cls = type(c).__name__
            if cls in ("SingleCoil",):
                check(c, ("hot", "gnd"), "pickup")
            elif cls in ("Humbucker",):
                if getattr(c, "leads", 2) == 2:
                    check(c, ("hot", "gnd"), "humbucker")
                else:
                    check(c, ("north_start", "north_finish",
                              "south_start", "south_finish", "bare"),
                          "humbucker")
            elif cls == "Jack":
                tabs = ("tip", "sleeve")
                if getattr(c, "kind", "TS") == "TRS":
                    tabs = tabs + ("ring",)
                check(c, tabs, "jack")

        if warnings:
            import sys
            for w in warnings:
                sys.stderr.write(f"[wiring] UNWIRED: {w}\n")
            if strict:
                raise RuntimeError(
                    f"assert_complete failed: {len(warnings)} unwired points"
                )
        return warnings

    def junction(self, x: float, y: float) -> None:
        """Mark an electrical junction (wires joining) with a filled dot."""
        self._svg.append(dw.Circle(x, y, 3.4, fill="#1a1a1a"))

    def note(self, x: float, y: float, text: str, size: int = 10,
             anchor: str = "start", color: str = "#444") -> None:
        """Free-floating text annotation."""
        self._svg.append(dw.Text(
            text, size, x, y,
            text_anchor=anchor, font_family="sans-serif", fill=color,
        ))

    def truth_table(self, x: float, y: float, title: str,
                    rows: list[tuple[str, str]], width: float = 350) -> None:
        """Draw a compact truth/mode table next to a switch.

        Each row is `(left, right)` — left is a short label (e.g. "POS A:"),
        right is the behavior text. Use an empty `left` for continuation rows
        of the previous position. Use `▸` / `⇒` in the right-column text to
        separate "what closes" from "what that means."

        Example
        -------
            d.truth_table(680, 78, "MOD switch — Series / Parallel", [
                ("POS A:", "T3↔T1 closes  →  neck-gnd meets GND"),
                ("",       "T4↔T2 closes  →  bridge-hot meets Vol-B.lug(3)"),
                ("",       "⇒ PARALLEL (standard J-Bass V/V/T)"),
                ("POS B:", "T3↔T5 and T4↔T6 close  —  jumper ties them"),
                ("",       "⇒ SERIES: neck-gnd = bridge-hot, coils joined"),
            ])
        """
        pad = 8
        row_h = 14
        title_h = 15
        total_h = pad * 2 + title_h + 6 + row_h * len(rows)

        self._svg.append(dw.Rectangle(
            x, y, width, total_h,
            fill="#fafafa", stroke="#999", stroke_width=1, rx=4,
        ))
        self._svg.append(dw.Text(
            title, 11, x + pad, y + pad + 10,
            font_family="sans-serif", font_weight="bold", fill="#111",
        ))
        sep_y = y + pad + title_h + 1
        self._svg.append(dw.Line(
            x + pad, sep_y, x + width - pad, sep_y,
            stroke="#ccc", stroke_width=1,
        ))
        for i, (left, right) in enumerate(rows):
            row_y = sep_y + 6 + i * row_h
            if left:
                self._svg.append(dw.Text(
                    left, 9, x + pad, row_y + 9,
                    font_family="sans-serif", font_weight="bold", fill="#333",
                ))
            if right:
                self._svg.append(dw.Text(
                    right, 9, x + pad + 52, row_y + 9,
                    font_family="sans-serif", fill="#333",
                ))

    def legend(self, x: float, y: float, entries: list[tuple[str, str]]) -> None:
        """Draw a small color-legend box. entries = [(color_hex, label), ...]."""
        pad = 6
        line_h = 16
        w = 180
        h = pad * 2 + line_h * len(entries)
        self._svg.append(dw.Rectangle(
            x, y, w, h, fill="#fafafa", stroke="#bbb", stroke_width=1, rx=4,
        ))
        for i, (color, text) in enumerate(entries):
            cy = y + pad + i * line_h + line_h / 2
            self._svg.append(dw.Line(
                x + pad, cy, x + pad + 22, cy,
                stroke=color, stroke_width=3, stroke_linecap="round",
            ))
            self._svg.append(dw.Text(
                text, 10, x + pad + 30, cy + 3,
                font_family="sans-serif", fill="#222",
            ))

    def save_svg(self, path: str | Path) -> Path:
        path = Path(path)
        self._svg.save_svg(str(path))
        return path


def _is_light(color: str) -> bool:
    c = color.lower().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return False
    # luminance heuristic
    return (r * 0.299 + g * 0.587 + b * 0.114) > 200


class Pot(Component):
    """Potentiometer viewed from the back. Circle body + three numbered lugs.

    lug(1) = CCW, lug(2) = wiper, lug(3) = CW.
    .casing exposes a solder-able point on the back of the pot (ground return).
    """

    RADIUS = 40

    def __init__(self, x, y, label: str, value: str = "500kA"):
        super().__init__(x, y, label)
        self.value = value
        # SVG: 0°=right (east), 90°=down (south), 180°=left, 270°=up (north).
        # Lugs arranged along the bottom arc with lug 1 on the LEFT (CCW end)
        # and lug 3 on the RIGHT (CW end) — standard pot-back numbering.
        self._lug_angles = (120, 90, 60)  # lug 1, 2, 3 from left to right
        self._lugs = tuple(
            self._radial(a, self.RADIUS + 20) for a in self._lug_angles
        )
        # Casing (ground) solder tab drawn to the LEFT of the pot
        # (keeps clear of the label above and the value/lug numbers below)
        self._casing = self._radial(180, self.RADIUS + 18)
        self._top = (x, y - self.RADIUS)

    def _radial(self, deg: float, r: float) -> tuple[float, float]:
        a = math.radians(deg)
        return (self.x + r * math.cos(a), self.y + r * math.sin(a))

    def lug(self, n: int) -> tuple[float, float]:
        if n not in (1, 2, 3):
            raise ValueError(f"Pot has lugs 1..3, got {n}")
        return self._lugs[n - 1]

    @property
    def casing(self) -> tuple[float, float]:
        return self._casing

    @property
    def top(self) -> tuple[float, float]:
        return self._top

    def bbox(self, margin: float = 0):
        r = self.RADIUS + margin
        return (self.x - r, self.y - r, self.x + r, self.y + r)

    def draw(self, svg):
        # body
        svg.append(dw.Circle(
            self.x, self.y, self.RADIUS,
            fill="#f5f5f5", stroke="#111", stroke_width=2,
        ))
        # CW rotation indicator — small curved arrow around the shaft showing
        # the direction the wiper moves when the knob is turned CW FROM THE
        # FRONT (= CCW in this back view). For a volume pot wired "hot→lug 3,
        # gnd→lug 1" this means CW-from-front moves the wiper toward lug 3
        # (more signal = louder). So: arrow starts near lug 1 (quiet end)
        # and curls over the TOP to end with an arrowhead near lug 3 (loud).
        cw_r = 14
        start_deg, end_deg = 120, 60    # lug 1 side → lug 3 side
        sx = self.x + cw_r * math.cos(math.radians(start_deg))
        sy = self.y + cw_r * math.sin(math.radians(start_deg))
        ex = self.x + cw_r * math.cos(math.radians(end_deg))
        ey = self.y + cw_r * math.sin(math.radians(end_deg))
        # SVG arc: large-arc=1 (long way, through the TOP of the pot),
        # sweep=0 (CCW visually in SVG's y-down coordinate system).
        svg.append(dw.Path(stroke="#999", stroke_width=1.3, fill="none")
                   .M(sx, sy).A(cw_r, cw_r, 0, 1, 0, ex, ey))
        # Arrowhead at endpoint, tangent to the arc at angle 60° going CCW.
        # Tangent direction: for CCW motion in SVG, rotate radial vector 90° CW.
        # Radial at 60° = (cos60, sin60) = (+0.5, +0.866). Rotate 90° CW in
        # SVG coords = (y, -x) = (+0.866, -0.5). So tangent points UP-RIGHT —
        # which is exactly "exiting the arc outward toward lug 3's 4-o'clock
        # region." Draw two short legs forming a V pointing along tangent.
        tx, ty = 0.866, -0.5
        head = 5
        # Two sides of the arrowhead, each rotated ±30° from the tangent.
        for sign in (+1, -1):
            a = math.atan2(ty, tx) + sign * math.radians(150)
            hx = ex + head * math.cos(a)
            hy = ey + head * math.sin(a)
            svg.append(dw.Line(ex, ey, hx, hy,
                               stroke="#999", stroke_width=1.3,
                               stroke_linecap="round"))
        # "CW (front)" caption at the top of the arc, inside the circle.
        svg.append(dw.Text(
            "CW (front)", 7, self.x, self.y - cw_r - 1,
            text_anchor="middle", font_family="sans-serif",
            fill="#999", font_style="italic",
        ))
        # shaft (drawn LAST so it sits on top of the arrow)
        svg.append(dw.Circle(
            self.x, self.y, 6, fill="#888", stroke="#111", stroke_width=1,
        ))
        # small "back of pot" hatching to hint at casing
        for r in (28, 22, 16):
            svg.append(dw.Circle(
                self.x, self.y, r, fill="none",
                stroke="#ddd", stroke_width=0.6,
            ))
        # label above
        svg.append(dw.Text(
            self.label, 12, self.x, self.y - self.RADIUS - 10,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        # value inside, below shaft
        svg.append(dw.Text(
            self.value, 9, self.x, self.y + 20,
            text_anchor="middle", font_family="sans-serif", fill="#555",
        ))
        # casing solder hook (the pot body = ground return)
        svg.append(dw.Circle(
            self._casing[0], self._casing[1], 9,
            fill="#666", stroke="#111", stroke_width=1,
        ))
        svg.append(dw.Text(
            "GND", 7, self._casing[0], self._casing[1] + 2.5,
            text_anchor="middle", font_family="sans-serif",
            fill="#fff", font_weight="bold",
        ))
        # lugs — tab line + pad + number
        for i, (lx, ly) in enumerate(self._lugs, start=1):
            a = math.atan2(ly - self.y, lx - self.x)
            ex = self.x + self.RADIUS * math.cos(a)
            ey = self.y + self.RADIUS * math.sin(a)
            svg.append(dw.Line(
                ex, ey, lx, ly, stroke="#111", stroke_width=2,
            ))
            svg.append(dw.Circle(
                lx, ly, 5.5, fill="#fff", stroke="#111", stroke_width=1.2,
            ))
            # number — placed further out along the same radial
            nx = self.x + (self.RADIUS + 36) * math.cos(a)
            ny = self.y + (self.RADIUS + 36) * math.sin(a)
            # white halo for legibility against wires
            svg.append(dw.Text(
                str(i), 14, nx, ny + 5,
                text_anchor="middle", font_family="sans-serif",
                font_weight="bold", fill="#fff",
                stroke="#fff", stroke_width=3.5,
            ))
            svg.append(dw.Text(
                str(i), 14, nx, ny + 5,
                text_anchor="middle", font_family="sans-serif",
                font_weight="bold", fill="#111",
            ))


class DPDT(Component):
    """Double-pole double-throw switch.

    Terminal layout (2 cols x 3 rows):
        [1] [2]    throw A
        [3] [4]    commons (poles)
        [5] [6]    throw B

    throws=2 → ON-ON (no middle position).
    throws=3 → ON-OFF-ON (middle position opens both poles).
    """

    WIDTH = 46
    HEIGHT = 94

    def __init__(self, x, y, label: str, throws: int = 2):
        super().__init__(x, y, label)
        if throws not in (2, 3):
            raise ValueError("DPDT throws must be 2 (ON-ON) or 3 (ON-OFF-ON)")
        self.throws = throws
        dx, dy = 13, 28
        self._terms = (
            (x - dx, y - dy),  # 1
            (x + dx, y - dy),  # 2
            (x - dx, y),       # 3  common
            (x + dx, y),       # 4  common
            (x - dx, y + dy),  # 5
            (x + dx, y + dy),  # 6
        )

    def term(self, n: int) -> tuple[float, float]:
        if n not in range(1, 7):
            raise ValueError(f"DPDT has terminals 1..6, got {n}")
        return self._terms[n - 1]

    def bbox(self, margin: float = 0):
        return (self.x - self.WIDTH / 2 - margin,
                self.y - self.HEIGHT / 2 - margin,
                self.x + self.WIDTH / 2 + margin,
                self.y + self.HEIGHT / 2 + margin)

    def draw(self, svg):
        svg.append(dw.Rectangle(
            self.x - self.WIDTH / 2, self.y - self.HEIGHT / 2,
            self.WIDTH, self.HEIGHT,
            fill="#f5f5f5", stroke="#111", stroke_width=2, rx=4,
        ))
        # label
        svg.append(dw.Text(
            self.label, 11, self.x, self.y - self.HEIGHT / 2 - 14,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        svg.append(dw.Text(
            f"DPDT {'ON-ON' if self.throws == 2 else 'ON-OFF-ON'}",
            8, self.x, self.y - self.HEIGHT / 2 - 2,
            text_anchor="middle", font_family="sans-serif", fill="#666",
        ))
        # Terminals. Commons (T3, T4) are filled with a soft yellow so
        # the reader can spot them at a glance, WITHOUT a shaded bar or
        # dashed rings joining them — those decorations made the two
        # commons look electrically connected, which they're NOT.
        common_fill = "#fff3b0"   # soft yellow — common/pole terminal
        throw_fill  = "#ffffff"   # plain white — throw terminal
        for i, (tx, ty) in enumerate(self._terms, start=1):
            fill = common_fill if i in (3, 4) else throw_fill
            svg.append(dw.Circle(
                tx, ty, 6, fill=fill, stroke="#111", stroke_width=1.4,
            ))
            svg.append(dw.Text(
                str(i), 10, tx, ty + 3.2,
                text_anchor="middle", font_family="sans-serif",
                font_weight="bold", fill="#111",
            ))


class PushPullPot(Component):
    """Push-pull pot: a Pot with a DPDT mechanically stacked on the same shaft.

    Drawn as Pot + DPDT side-by-side connected with a dashed "same shaft" line.
    .lug(n) forwards to the pot, .term(n) forwards to the switch.
    """

    def __init__(self, x, y, label: str, value: str = "500kA", throws: int = 2):
        super().__init__(x, y, label)
        self.pot = Pot(x, y, label, value)
        self.switch = DPDT(x + 90, y, f"{label} (push/pull)", throws)

    def lug(self, n): return self.pot.lug(n)
    def term(self, n): return self.switch.term(n)

    @property
    def casing(self): return self.pot.casing

    def bbox(self, margin: float = 0):
        p = self.pot.bbox(margin)
        s = self.switch.bbox(margin)
        return (min(p[0], s[0]), min(p[1], s[1]),
                max(p[2], s[2]), max(p[3], s[3]))

    def draw(self, svg):
        self.pot.draw(svg)
        self.switch.draw(svg)
        svg.append(dw.Line(
            self.pot.x + Pot.RADIUS, self.pot.y,
            self.switch.x - DPDT.WIDTH / 2, self.switch.y,
            stroke="#999", stroke_width=1.2, stroke_dasharray="4,3",
        ))
        svg.append(dw.Text(
            "same shaft", 8,
            (self.pot.x + Pot.RADIUS + self.switch.x - DPDT.WIDTH / 2) / 2,
            self.pot.y - 6,
            text_anchor="middle", font_family="sans-serif",
            font_style="italic", fill="#777",
        ))


class SingleCoil(Component):
    """Single-coil pickup. Vertical rectangle with pole pieces along the centerline.

    Two leads exit from the bottom: .hot (left, Fender white) and .gnd (right, black).
    """

    WIDTH = 36
    HEIGHT = 96
    DEFAULT_POLES = 4  # J-Bass & P-Bass have 4; Strat single-coils have 6

    def __init__(self, x, y, label: str, poles: int = None,
                 hot_color: str = None, gnd_color: str = None):
        super().__init__(x, y, label)
        self.poles = poles if poles is not None else self.DEFAULT_POLES
        self.hot_color = hot_color or WireColor.PICKUP_HOT_WHITE
        self.gnd_color = gnd_color or WireColor.PICKUP_GROUND
        self._hot = (x - 9, y + self.HEIGHT / 2 + 22)
        self._gnd = (x + 9, y + self.HEIGHT / 2 + 22)

    @property
    def hot(self): return self._hot
    @property
    def gnd(self): return self._gnd

    def bbox(self, margin: float = 0):
        return (self.x - self.WIDTH / 2 - margin,
                self.y - self.HEIGHT / 2 - margin,
                self.x + self.WIDTH / 2 + margin,
                self.y + self.HEIGHT / 2 + margin)

    def draw(self, svg):
        svg.append(dw.Rectangle(
            self.x - self.WIDTH / 2, self.y - self.HEIGHT / 2,
            self.WIDTH, self.HEIGHT,
            fill="#d8d8d8", stroke="#111", stroke_width=2, rx=3,
        ))
        svg.append(dw.Text(
            self.label, 11, self.x, self.y - self.HEIGHT / 2 - 8,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        # pole pieces along centerline
        inner = self.HEIGHT - 24
        step = inner / (self.poles - 1) if self.poles > 1 else 0
        start_y = self.y - inner / 2
        for i in range(self.poles):
            svg.append(dw.Circle(
                self.x, start_y + i * step, 3.6,
                fill="#888", stroke="#444", stroke_width=0.8,
            ))
        # leads
        body_bottom = self.y + self.HEIGHT / 2
        # hot (left) — if the lead color is light, draw a darker outline FIRST
        # so the light-colored wire reads clearly against a white canvas.
        if _is_light(self.hot_color):
            svg.append(dw.Line(
                self.x - 9, body_bottom, self._hot[0], self._hot[1],
                stroke="#2a2a2a", stroke_width=4.0,
            ))
        svg.append(dw.Line(
            self.x - 9, body_bottom, self._hot[0], self._hot[1],
            stroke=self.hot_color, stroke_width=2.4,
        ))
        svg.append(dw.Circle(
            *self._hot, 3.4, fill=self.hot_color,
            stroke="#111", stroke_width=0.9,
        ))
        svg.append(dw.Text(
            "HOT", 8, self._hot[0] - 8, self._hot[1] + 3,
            text_anchor="end", font_family="sans-serif",
            fill="#444", font_weight="bold",
        ))
        # gnd (right)
        svg.append(dw.Line(
            self.x + 9, body_bottom, self._gnd[0], self._gnd[1],
            stroke=self.gnd_color, stroke_width=2.4,
        ))
        svg.append(dw.Circle(
            *self._gnd, 3.4, fill=self.gnd_color,
            stroke="#111", stroke_width=0.9,
        ))
        svg.append(dw.Text(
            "GND", 8, self._gnd[0] + 8, self._gnd[1] + 3,
            text_anchor="start", font_family="sans-serif",
            fill="#444", font_weight="bold",
        ))


class Humbucker(Component):
    """Humbucker pickup: horizontal rectangle with two rows of 6 pole pieces.

    leads=2: exposes .hot and .gnd.
    leads=4: exposes .north_start, .north_finish, .south_start, .south_finish,
             and .bare (shield). Seymour Duncan color code:
               N-S=black, N-F=white, S-S=red, S-F=green, bare=shield.
    """

    WIDTH = 108
    HEIGHT = 48

    def __init__(self, x, y, label: str, leads: int = 2,
                 hot_color: str | None = None, gnd_color: str | None = None):
        super().__init__(x, y, label)
        if leads not in (2, 4):
            raise ValueError("Humbucker leads must be 2 or 4")
        self.leads = leads
        # Only meaningful for leads=2. 4-lead humbuckers use the fixed SD color code.
        self.hot_color = hot_color or "#1a1a1a"
        self.gnd_color = gnd_color or WireColor.SD_SOUTH_FINISH
        by = y + self.HEIGHT / 2 + 28
        if leads == 2:
            self._hot = (x - 14, by)
            self._gnd = (x + 14, by)
        else:
            self._north_start = (x - 36, by)
            self._north_finish = (x - 12, by)
            self._south_start = (x + 12, by)
            self._south_finish = (x + 36, by)
            self._bare = (x, by + 22)

    @property
    def hot(self):
        if self.leads != 2:
            raise AttributeError(".hot requires leads=2 humbucker")
        return self._hot

    @property
    def gnd(self):
        if self.leads != 2:
            raise AttributeError(".gnd requires leads=2 humbucker")
        return self._gnd

    @property
    def north_start(self):
        if self.leads != 4:
            raise AttributeError(".north_start requires leads=4 humbucker")
        return self._north_start

    @property
    def north_finish(self):
        if self.leads != 4:
            raise AttributeError(".north_finish requires leads=4 humbucker")
        return self._north_finish

    @property
    def south_start(self):
        if self.leads != 4:
            raise AttributeError(".south_start requires leads=4 humbucker")
        return self._south_start

    @property
    def south_finish(self):
        if self.leads != 4:
            raise AttributeError(".south_finish requires leads=4 humbucker")
        return self._south_finish

    @property
    def bare(self):
        if self.leads != 4:
            raise AttributeError(".bare requires leads=4 humbucker")
        return self._bare

    def bbox(self, margin: float = 0):
        return (self.x - self.WIDTH / 2 - margin,
                self.y - self.HEIGHT / 2 - margin,
                self.x + self.WIDTH / 2 + margin,
                self.y + self.HEIGHT / 2 + margin)

    def draw(self, svg):
        svg.append(dw.Rectangle(
            self.x - self.WIDTH / 2, self.y - self.HEIGHT / 2,
            self.WIDTH, self.HEIGHT,
            fill="#4a4a4a", stroke="#111", stroke_width=2, rx=4,
        ))
        svg.append(dw.Text(
            self.label, 11, self.x, self.y - self.HEIGHT / 2 - 8,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        # two rows of 6 pole pieces
        for ry in (self.y - 10, self.y + 10):
            for i in range(6):
                px = self.x - 40 + i * 16
                svg.append(dw.Circle(
                    px, ry, 3.2, fill="#ccc", stroke="#222", stroke_width=0.6,
                ))
        # coil divider line
        svg.append(dw.Line(
            self.x, self.y - self.HEIGHT / 2 + 4,
            self.x, self.y + self.HEIGHT / 2 - 4,
            stroke="#888", stroke_width=0.6, stroke_dasharray="2,2",
        ))
        svg.append(dw.Text(
            "N", 7, self.x - self.WIDTH / 4, self.y - self.HEIGHT / 2 + 8,
            text_anchor="middle", font_family="sans-serif", fill="#bbb",
        ))
        svg.append(dw.Text(
            "S", 7, self.x + self.WIDTH / 4, self.y - self.HEIGHT / 2 + 8,
            text_anchor="middle", font_family="sans-serif", fill="#bbb",
        ))
        # leads
        body_bottom = self.y + self.HEIGHT / 2
        if self.leads == 2:
            leads = [
                (self.hot_color, "HOT", self._hot, self.x - 14),
                (self.gnd_color, "GND", self._gnd, self.x + 14),
            ]
        else:
            leads = [
                (WireColor.SD_NORTH_START, "N-S", self._north_start, self.x - 36),
                (WireColor.SD_NORTH_FINISH, "N-F", self._north_finish, self.x - 12),
                (WireColor.SD_SOUTH_START, "S-S", self._south_start, self.x + 12),
                (WireColor.SD_SOUTH_FINISH, "S-F", self._south_finish, self.x + 36),
            ]
        for color, tag, pt, top_x in leads:
            # If the lead color is light, draw a darker outline FIRST so the
            # wire reads clearly against the white canvas.
            if _is_light(color):
                svg.append(dw.Line(
                    top_x, body_bottom, pt[0], pt[1],
                    stroke="#2a2a2a", stroke_width=4.0,
                ))
            svg.append(dw.Line(
                top_x, body_bottom, pt[0], pt[1],
                stroke=color, stroke_width=2.4,
            ))
            svg.append(dw.Circle(
                *pt, 3.4, fill=color, stroke="#111", stroke_width=0.8,
            ))
            svg.append(dw.Text(
                tag, 8, pt[0], pt[1] + 14,
                text_anchor="middle", font_family="sans-serif",
                fill="#333", font_weight="bold",
            ))
        if self.leads == 4:
            svg.append(dw.Line(
                self.x, body_bottom, self._bare[0], self._bare[1],
                stroke=WireColor.SHIELD, stroke_width=2,
                stroke_dasharray="3,2",
            ))
            svg.append(dw.Circle(
                *self._bare, 3.4, fill=WireColor.SHIELD,
                stroke="#111", stroke_width=0.8,
            ))
            svg.append(dw.Text(
                "bare (shield)", 8, self._bare[0] + 10, self._bare[1] + 3,
                text_anchor="start", font_family="sans-serif", fill="#444",
            ))


class Jack(Component):
    """Output jack. kind='TS' (mono) or 'TRS' (stereo).

    Exposes .tip, .sleeve (and .ring for TRS).
    """

    RADIUS = 26

    def __init__(self, x, y, label: str = "Output Jack", kind: str = "TS"):
        super().__init__(x, y, label)
        if kind not in ("TS", "TRS"):
            raise ValueError("Jack kind must be 'TS' or 'TRS'")
        self.kind = kind
        dx = self.RADIUS + 28
        if kind == "TS":
            self._tip = (x + dx, y - 18)
            self._sleeve = (x + dx, y + 18)
        else:
            self._tip = (x + dx, y - 22)
            self._ring = (x + dx, y)
            self._sleeve = (x + dx, y + 22)

    @property
    def tip(self): return self._tip
    @property
    def sleeve(self): return self._sleeve
    @property
    def ring(self):
        if self.kind != "TRS":
            raise AttributeError("ring requires TRS jack")
        return self._ring

    def bbox(self, margin: float = 0):
        r = self.RADIUS + margin
        return (self.x - r, self.y - r, self.x + r, self.y + r)

    def draw(self, svg):
        svg.append(dw.Circle(
            self.x, self.y, self.RADIUS,
            fill="#f5f5f5", stroke="#111", stroke_width=2,
        ))
        # plug silhouette hint
        svg.append(dw.Rectangle(
            self.x - self.RADIUS + 4, self.y - 6, self.RADIUS - 4, 12,
            fill="#ddd", stroke="#888", stroke_width=1,
        ))
        svg.append(dw.Text(
            self.label, 11, self.x, self.y - self.RADIUS - 10,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        svg.append(dw.Text(
            self.kind, 8, self.x, self.y + 4,
            text_anchor="middle", font_family="sans-serif", fill="#666",
        ))
        pairs = [("T  (tip)", self._tip), ("S  (sleeve)", self._sleeve)]
        if self.kind == "TRS":
            pairs.insert(1, ("R  (ring)", self._ring))
        for name, pt in pairs:
            a = math.atan2(pt[1] - self.y, pt[0] - self.x)
            ex = self.x + self.RADIUS * math.cos(a)
            ey = self.y + self.RADIUS * math.sin(a)
            svg.append(dw.Line(
                ex, ey, pt[0], pt[1], stroke="#111", stroke_width=1.8,
            ))
            svg.append(dw.Circle(
                *pt, 5, fill="#fff", stroke="#111", stroke_width=1.2,
            ))
            svg.append(dw.Text(
                name, 9, pt[0] + 10, pt[1] + 3,
                text_anchor="start", font_family="sans-serif",
                fill="#222", font_weight="bold",
            ))


class Capacitor(Component):
    """Non-polar capacitor. .a and .b are the two solder leads."""

    WIDTH = 36

    def __init__(self, x, y, value: str = "0.047\u00b5F", label: str | None = None):
        super().__init__(x, y, label or f"Cap {value}")
        self.value = value
        self._a = (x - self.WIDTH / 2 - 14, y)
        self._b = (x + self.WIDTH / 2 + 14, y)

    @property
    def a(self): return self._a
    @property
    def b(self): return self._b

    def bbox(self, margin: float = 0):
        return (self.x - self.WIDTH / 2 - margin, self.y - 14 - margin,
                self.x + self.WIDTH / 2 + margin, self.y + 14 + margin)

    def draw(self, svg):
        plate_h = 22
        # two parallel plates
        svg.append(dw.Line(
            self.x - 3, self.y - plate_h / 2, self.x - 3, self.y + plate_h / 2,
            stroke="#111", stroke_width=3,
        ))
        svg.append(dw.Line(
            self.x + 3, self.y - plate_h / 2, self.x + 3, self.y + plate_h / 2,
            stroke="#111", stroke_width=3,
        ))
        # leads
        svg.append(dw.Line(
            self._a[0], self._a[1], self.x - 3, self.y,
            stroke="#111", stroke_width=1.8,
        ))
        svg.append(dw.Line(
            self.x + 3, self.y, self._b[0], self._b[1],
            stroke="#111", stroke_width=1.8,
        ))
        # pads
        svg.append(dw.Circle(
            *self._a, 4.4, fill="#fff", stroke="#111", stroke_width=1.2,
        ))
        svg.append(dw.Circle(
            *self._b, 4.4, fill="#fff", stroke="#111", stroke_width=1.2,
        ))
        # value label
        svg.append(dw.Text(
            self.value, 11, self.x, self.y + plate_h / 2 + 14,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))


class Ground(Component):
    """Standard ground symbol (three descending bars). .point = the hook-up point."""

    def __init__(self, x, y, label: str = "GND"):
        super().__init__(x, y, label)
        self._point = (x, y)

    @property
    def point(self): return self._point

    def bbox(self, margin: float = 0):
        return (self.x - 14 - margin, self.y - 2 - margin,
                self.x + 14 + margin, self.y + 30 + margin)

    def draw(self, svg):
        # short stem
        svg.append(dw.Line(
            self.x, self.y, self.x, self.y + 10,
            stroke="#111", stroke_width=2,
        ))
        # three bars
        for w, dy in ((22, 10), (14, 15), (6, 20)):
            svg.append(dw.Line(
                self.x - w / 2, self.y + dy, self.x + w / 2, self.y + dy,
                stroke="#111", stroke_width=2,
            ))
        svg.append(dw.Text(
            self.label, 10, self.x, self.y + 34,
            text_anchor="middle", font_family="sans-serif",
            fill="#555", font_weight="bold",
        ))
        # hook marker
        svg.append(dw.Circle(
            self.x, self.y, 3.2, fill="#111",
        ))


class ThreeWay(Component):
    """Gibson-style 3-way toggle (pickup selector).

    Four solder tabs:
      .neck   – wire the neck pickup's hot signal here
      .bridge – wire the bridge pickup's hot signal here
      .common – the selected pickup(s) exit here
      .gnd    – ground tab on the switch body
    """

    WIDTH = 78
    HEIGHT = 44

    def __init__(self, x, y, label: str = "3-Way Toggle"):
        super().__init__(x, y, label)
        self._neck = (x - 26, y + 14)
        self._common = (x, y + 14)
        self._bridge = (x + 26, y + 14)
        self._gnd = (x, y - self.HEIGHT / 2 - 12)

    @property
    def neck(self): return self._neck
    @property
    def bridge(self): return self._bridge
    @property
    def common(self): return self._common
    @property
    def gnd(self): return self._gnd

    def bbox(self, margin: float = 0):
        return (self.x - self.WIDTH / 2 - margin,
                self.y - self.HEIGHT / 2 - margin,
                self.x + self.WIDTH / 2 + margin,
                self.y + self.HEIGHT / 2 + margin)

    def draw(self, svg):
        svg.append(dw.Rectangle(
            self.x - self.WIDTH / 2, self.y - self.HEIGHT / 2,
            self.WIDTH, self.HEIGHT,
            fill="#f5f5f5", stroke="#111", stroke_width=2, rx=4,
        ))
        svg.append(dw.Text(
            self.label, 10, self.x, self.y - self.HEIGHT / 2 - 6,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        for tag, pt in (("N", self._neck), ("C", self._common),
                        ("B", self._bridge), ("G", self._gnd)):
            svg.append(dw.Circle(
                *pt, 5, fill="#fff", stroke="#111", stroke_width=1.2,
            ))
            svg.append(dw.Text(
                tag, 9, pt[0], pt[1] + 3,
                text_anchor="middle", font_family="sans-serif",
                font_weight="bold", fill="#111",
            ))


class FiveWay(Component):
    """Fender-style 5-way blade switch (Strat selector).

    Two poles, each with 1 common + 4 individual throws. Use:
      .a(1..4) and .b(1..4) — the throws on pole A and pole B respectively
      .a_common, .b_common  — the wipers

    Standard Strat signal routing uses pole A for the pickup-to-volume path.
    Pole B is typically free for push-pull / series-parallel / "7-sound" mods.
    Blade positions (1 = toward-neck, 5 = toward-bridge) select:
      pos 1: a1  only
      pos 2: a1 + a2 shorted (neck + mid combined at wiper)
      pos 3: a2  only (mid)
      pos 4: a2 + a3 shorted (mid + bridge combined)
      pos 5: a3  only
    (So pole A typically uses only throws 1–3 + common; throw 4 is often unused.)
    """

    WIDTH = 140
    HEIGHT = 56

    def __init__(self, x, y, label: str = "5-Way Blade"):
        super().__init__(x, y, label)
        xs = (x - 48, x - 28, x - 8, x + 12)
        self._a = tuple((xi, y - 14) for xi in xs)
        self._b = tuple((xi, y + 14) for xi in xs)
        self._a_common = (x + 50, y - 14)
        self._b_common = (x + 50, y + 14)
        # Switch-body ground tab (above the switch, outside the bbox) so any
        # diagram that wants to ground the switch chassis has a canonical node.
        self._gnd = (x, y - self.HEIGHT / 2 - 10)

    def a(self, n):
        if n not in range(1, 5):
            raise ValueError("FiveWay pole A throws 1..4")
        return self._a[n - 1]

    def b(self, n):
        if n not in range(1, 5):
            raise ValueError("FiveWay pole B throws 1..4")
        return self._b[n - 1]

    @property
    def a_common(self): return self._a_common
    @property
    def b_common(self): return self._b_common
    @property
    def gnd(self): return self._gnd

    def bbox(self, margin: float = 0):
        return (self.x - self.WIDTH / 2 - margin,
                self.y - self.HEIGHT / 2 - margin,
                self.x + self.WIDTH / 2 + margin,
                self.y + self.HEIGHT / 2 + margin)

    def draw(self, svg):
        svg.append(dw.Rectangle(
            self.x - self.WIDTH / 2, self.y - self.HEIGHT / 2,
            self.WIDTH, self.HEIGHT,
            fill="#f5f5f5", stroke="#111", stroke_width=2, rx=4,
        ))
        svg.append(dw.Text(
            self.label, 10, self.x, self.y - self.HEIGHT / 2 - 6,
            text_anchor="middle", font_family="sans-serif",
            font_weight="bold", fill="#111",
        ))
        # throw terminals
        for i, pt in enumerate(self._a, start=1):
            svg.append(dw.Circle(
                *pt, 4.5, fill="#fff", stroke="#111", stroke_width=1,
            ))
            svg.append(dw.Text(
                f"A{i}", 7, pt[0], pt[1] + 2.5,
                text_anchor="middle", font_family="sans-serif",
                fill="#111", font_weight="bold",
            ))
        for i, pt in enumerate(self._b, start=1):
            svg.append(dw.Circle(
                *pt, 4.5, fill="#fff", stroke="#111", stroke_width=1,
            ))
            svg.append(dw.Text(
                f"B{i}", 7, pt[0], pt[1] + 2.5,
                text_anchor="middle", font_family="sans-serif",
                fill="#111", font_weight="bold",
            ))
        # commons
        for pt, tag in ((self._a_common, "A-C"), (self._b_common, "B-C")):
            svg.append(dw.Circle(
                *pt, 5.5, fill="#ffd94a", stroke="#111", stroke_width=1.3,
            ))
            svg.append(dw.Text(
                tag, 8, pt[0], pt[1] + 3,
                text_anchor="middle", font_family="sans-serif",
                fill="#111", font_weight="bold",
            ))
        # chassis-ground tab
        svg.append(dw.Circle(
            *self._gnd, 4, fill="#fff", stroke="#111", stroke_width=1,
        ))
        svg.append(dw.Text(
            "G", 7, self._gnd[0], self._gnd[1] + 2.5,
            text_anchor="middle", font_family="sans-serif",
            fill="#111", font_weight="bold",
        ))


class GroundRail(Component):
    """Visible horizontal ground bus. Use ONE per diagram instead of scattered
    wires converging on a single Ground point — reads much cleaner.

    Place the rail below the control row. Every ground wire terminates on it
    via `rail.tap(x)`, which returns the (x, y) point on the rail at column
    `x` (clamped to the rail's extent). The rail draws its own ground symbol
    at one end.

        rail = d.add(GroundRail(y=820, x_start=180, x_end=1240))
        d.wire(vol_n.casing, rail.tap(vol_n.x), color=WireColor.GROUND)

    Parameters
    ----------
    y : float
        The horizontal line's y coordinate.
    x_start, x_end : float
        Left and right extent of the rail.
    ground_at : "left" or "right"
        Which end of the rail carries the ground-symbol terminal.
    label : str
        Label shown below the ground symbol.
    """

    def __init__(self, y: float, x_start: float, x_end: float,
                 ground_at: str = "left", label: str = "Chassis GND"):
        if ground_at not in ("left", "right"):
            raise ValueError("ground_at must be 'left' or 'right'")
        self.rail_y = y
        self.x_start = x_start
        self.x_end = x_end
        self.ground_at = ground_at
        gx = x_start if ground_at == "left" else x_end
        super().__init__(gx, y, label)

    def tap(self, x: float) -> tuple[float, float]:
        """Return (x, rail_y) as a wire-able point on the rail at column `x`."""
        x = max(self.x_start, min(self.x_end, x))
        return (x, self.rail_y)

    def bbox(self, margin: float = 0):
        # a thin strip — wires routing vertically can approach from above,
        # but nothing should route horizontally across it except the rail itself.
        return (self.x_start - margin, self.rail_y - 3 - margin,
                self.x_end + margin, self.rail_y + 3 + margin)

    def draw(self, svg):
        # thick horizontal rail
        svg.append(dw.Line(
            self.x_start, self.rail_y, self.x_end, self.rail_y,
            stroke="#1a1a1a", stroke_width=4.5, stroke_linecap="round",
        ))
        # rail end caps
        for ex in (self.x_start, self.x_end):
            svg.append(dw.Circle(
                ex, self.rail_y, 4, fill="#1a1a1a",
            ))
        # ground symbol hanging off the chosen end
        gx = self.x
        svg.append(dw.Line(
            gx, self.rail_y, gx, self.rail_y + 16,
            stroke="#1a1a1a", stroke_width=3,
        ))
        for w, dy in ((30, 16), (20, 22), (10, 28)):
            svg.append(dw.Line(
                gx - w / 2, self.rail_y + dy, gx + w / 2, self.rail_y + dy,
                stroke="#1a1a1a", stroke_width=3,
            ))
        svg.append(dw.Text(
            self.label, 11, gx, self.rail_y + 44,
            text_anchor="middle", font_family="sans-serif",
            fill="#333", font_weight="bold",
        ))


__all__ = [
    "WireColor", "Diagram", "route_around",
    "Pot", "PushPullPot", "DPDT",
    "SingleCoil", "Humbucker",
    "Jack", "Capacitor", "Ground", "GroundRail",
    "ThreeWay", "FiveWay",
]
