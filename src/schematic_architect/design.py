"""A design: blocks at integer positions (y up), each a palette role ("@primary") or a block state ("minecraft:oak_log[axis=x]").

Shapes take inclusive corners. Positions may be anywhere; the export moves the lowest corner to 0, 0, 0, and every
position inside the bounds that holds no block is air (a bot building it clears what stands there)."""

import math
import re
from collections import Counter

from .palettes import BLOCK_TIER, PALETTES, ROLES, TIERS

MAX_BLOCKS = 1_000_000
MAX_SHAPE_VOLUME = 4_000_000
UNDO_DEPTH = 20

_STATE = re.compile(r"^([a-z0-9_.-]+:)?[a-z0-9_./-]+(\[[a-z0-9_]+=[a-z0-9_]+(,[a-z0-9_]+=[a-z0-9_]+)*\])?$")
_TURN = {"north": "east", "east": "south", "south": "west", "west": "north"}
_MIRROR = {"x": {"east": "west", "west": "east"}, "z": {"north": "south", "south": "north"}}

Pos = tuple[int, int, int]


def parse_block(block: str) -> str | None:
    """The stored form of a block argument: "@role" for a palette role, a namespaced block state, or None for air."""
    block = block.strip().lower()
    if block in ROLES:
        return "@" + block
    if block.startswith("@") and block[1:] in ROLES:
        return block
    if not _STATE.match(block):
        raise ValueError(f"not a block or role: {block!r} (roles: {', '.join(ROLES)}; blocks like oak_log or "
                         "minecraft:oak_stairs[facing=north])")
    if ":" not in block.split("[")[0]:
        block = "minecraft:" + block
    return None if block.split("[")[0] in ("minecraft:air", "minecraft:cave_air") else block


def split_state(block: str) -> tuple[str, dict[str, str]]:
    name, _, props = block.partition("[")
    return name, dict(p.split("=") for p in props.rstrip("]").split(",")) if props else {}


def join_state(name: str, props: dict[str, str]) -> str:
    return name + ("[" + ",".join(f"{k}={v}" for k, v in props.items()) + "]" if props else "")


def turn_state(block: str, turns: int) -> str:
    """block turned a quarter clockwise (seen from above) turns times: its facing, axis and sign rotation."""
    if block.startswith("@") or turns % 4 == 0:
        return block
    name, props = split_state(block)
    for _ in range(turns % 4):
        if props.get("facing") in _TURN:
            props["facing"] = _TURN[props["facing"]]
        if props.get("axis") in ("x", "z"):
            props["axis"] = "z" if props["axis"] == "x" else "x"
        if "rotation" in props:
            props["rotation"] = str((int(props["rotation"]) + 4) % 16)
    return join_state(name, props)


def mirror_state(block: str, axis: str) -> str:
    """block mirrored across a plane facing axis ("x" flips east and west)."""
    if block.startswith("@") or axis == "y":
        return block
    name, props = split_state(block)
    if props.get("facing") in _MIRROR[axis]:
        props["facing"] = _MIRROR[axis][props["facing"]]
    # ponytail: stair shapes (inner_left/right) and multi-face blocks (fences, vines) keep their sides; fix by hand.
    return join_state(name, props)


def _corners(x1, y1, z1, x2, y2, z2):
    lo = (min(x1, x2), min(y1, y2), min(z1, z2))
    hi = (max(x1, x2), max(y1, y2), max(z1, z2))
    volume = (hi[0] - lo[0] + 1) * (hi[1] - lo[1] + 1) * (hi[2] - lo[2] + 1)
    if volume > MAX_SHAPE_VOLUME:
        raise ValueError(f"shape of {volume} blocks is over the limit of {MAX_SHAPE_VOLUME}")
    return lo, hi


class Design:
    def __init__(self, name: str, palette: str = "oak"):
        if palette not in PALETTES:
            raise ValueError(f"no palette {palette!r}; palettes: {', '.join(PALETTES)}")
        self.name = name
        self.palette = palette
        self.blocks: dict[Pos, str] = {}
        self._history: list[dict[Pos, str]] = []

    # --- editing -------------------------------------------------------------------------------------------------

    def checkpoint(self):
        """Keeps the blocks as they are for undo; call before each change."""
        self._history.append(dict(self.blocks))
        del self._history[:-UNDO_DEPTH]

    def undo(self) -> bool:
        if not self._history:
            return False
        self.blocks = self._history.pop()
        return True

    def put(self, pos: Pos, block: str | None):
        if block is None:
            self.blocks.pop(pos, None)
            return
        if pos not in self.blocks and len(self.blocks) >= MAX_BLOCKS:
            raise ValueError(f"design is over the limit of {MAX_BLOCKS} blocks")
        self.blocks[pos] = block

    def box(self, x1, y1, z1, x2, y2, z2, block, mode="solid") -> int:
        """Fills the box: mode solid, shell (all six faces), walls (the four sides) or frame (the twelve edges)."""
        if mode not in ("solid", "shell", "walls", "frame"):
            raise ValueError("mode is solid, shell, walls or frame")
        (ax, ay, az), (bx, by, bz) = _corners(x1, y1, z1, x2, y2, z2)
        n = 0
        for x in range(ax, bx + 1):
            for y in range(ay, by + 1):
                for z in range(az, bz + 1):
                    on = (x in (ax, bx), y in (ay, by), z in (az, bz))
                    if (mode == "solid" or (mode == "shell" and any(on)) or (mode == "walls" and (on[0] or on[2]))
                            or (mode == "frame" and sum(on) >= 2)):
                        self.put((x, y, z), block)
                        n += 1
        return n

    def line(self, x1, y1, z1, x2, y2, z2, block) -> int:
        steps = max(abs(x2 - x1), abs(y2 - y1), abs(z2 - z1))
        points = {(round(x1 + (x2 - x1) * i / steps), round(y1 + (y2 - y1) * i / steps), round(z1 + (z2 - z1) * i / steps))
                  for i in range(steps + 1)} if steps else {(x1, y1, z1)}
        for p in points:
            self.put(p, block)
        return len(points)

    def _shape(self, inside, lo: Pos, hi: Pos, block, solid=None) -> int:
        """Puts block on the positions in lo..hi that inside() takes. With solid, only on those with a neighbour solid()
        does not take: the shell of the shape, open where solid() goes on past inside() (a dome's cut face)."""
        _corners(*lo, *hi)
        n = 0
        for x in range(lo[0], hi[0] + 1):
            for y in range(lo[1], hi[1] + 1):
                for z in range(lo[2], hi[2] + 1):
                    if inside(x, y, z) and (solid is None or not all(
                            solid(x + dx, y + dy, z + dz)
                            for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)))):
                        self.put((x, y, z), block)
                        n += 1
        return n

    def sphere(self, cx, cy, cz, radius, block, hollow=False, half=None) -> int:
        """A ball around cx, cy, cz; half "top" or "bottom" keeps that half (a dome, a bowl)."""
        r2 = (radius + 0.5) ** 2
        ylo = cy if half == "top" else cy - radius
        yhi = cy if half == "bottom" else cy + radius

        def ball(x, y, z):
            return (x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 <= r2

        def inside(x, y, z):
            return ylo <= y <= yhi and ball(x, y, z)

        return self._shape(inside, (cx - radius, ylo, cz - radius), (cx + radius, yhi, cz + radius), block,
                           ball if hollow else None)

    def cylinder(self, x, y, z, radius, length, block, axis="y", hollow=False) -> int:
        """A cylinder whose first end is centred on x, y, z, running length blocks along +axis; hollow leaves a tube."""
        if axis not in ("x", "y", "z"):
            raise ValueError("axis is x, y or z")
        r2 = (radius + 0.5) ** 2
        a = "xyz".index(axis)
        centre = (x, y, z)
        lo = [c - radius for c in centre]
        hi = [c + radius for c in centre]
        lo[a], hi[a] = centre[a], centre[a] + length - 1

        def ring(p):
            return sum((p[i] - centre[i]) ** 2 for i in range(3) if i != a) <= r2

        def inside(px, py, pz):
            return lo[a] <= (px, py, pz)[a] <= hi[a] and ring((px, py, pz))

        # A tube is open at both ends: only the round side counts.
        return self._shape(inside, tuple(lo), tuple(hi), block, (lambda px, py, pz: ring((px, py, pz))) if hollow else None)

    def pyramid(self, x1, z1, x2, z2, y, block, hollow=False) -> int:
        """A stepped pyramid on the rectangle x1..x2, z1..z2 at height y, each layer one smaller on every side."""
        (ax, _, az), (bx, _, bz) = _corners(x1, y, z1, x2, y, z2)
        n = 0
        k = 0
        while ax + k <= bx - k and az + k <= bz - k:
            n += self.box(ax + k, y + k, az + k, bx - k, y + k, bz - k, block,
                          "solid" if not hollow or ax + k + 1 > bx - k - 1 or az + k + 1 > bz - k - 1 else "walls")
            k += 1
        return n

    def clear(self, x1, y1, z1, x2, y2, z2) -> int:
        (ax, ay, az), (bx, by, bz) = _corners(x1, y1, z1, x2, y2, z2)
        gone = [p for p in self.blocks if ax <= p[0] <= bx and ay <= p[1] <= by and az <= p[2] <= bz]
        for p in gone:
            del self.blocks[p]
        return len(gone)

    def replace(self, old: str | None, new: str | None) -> int:
        """Swaps every old for new; old matches by block name too, so "oak_log" takes oak_log[axis=x] as well."""
        hits = [p for p, b in self.blocks.items() if b == old or (old and "[" not in old and b.split("[")[0] == old)]
        for p in hits:
            self.put(p, new)
        return len(hits)

    def copy(self, x1, y1, z1, x2, y2, z2, dx, dy, dz, turns=0, mirror=None) -> int:
        """Copies the blocks of the box dx, dy, dz on, first mirrored ("x" or "z") and turned clockwise (seen from above)
        within the box; the copy's lowest corner lands at the box's lowest corner plus dx, dy, dz."""
        (ax, ay, az), (bx, by, bz) = _corners(x1, y1, z1, x2, y2, z2)
        sx, sz = bx - ax, bz - az
        moved = {}
        for (x, y, z), block in self.blocks.items():
            if not (ax <= x <= bx and ay <= y <= by and az <= z <= bz):
                continue
            lx, ly, lz = x - ax, y - ay, z - az
            if mirror == "x":
                lx, block = sx - lx, mirror_state(block, "x")
            elif mirror == "z":
                lz, block = sz - lz, mirror_state(block, "z")
            w, d = sx, sz
            for _ in range(turns % 4):
                lx, lz, w, d = d - lz, lx, d, w
            moved[(ax + dx + lx, ay + dy + ly, az + dz + lz)] = turn_state(block, turns)
        for p, block in moved.items():
            self.put(p, block)
        return len(moved)

    def symmetrize(self, axis: str, center: float | None = None) -> int:
        """Mirrors the blocks on the low side of the plane at center (the middle of the design by default) onto the
        high side, so the design is symmetric across it."""
        if axis not in ("x", "z"):
            raise ValueError("axis is x or z")
        a = "xyz".index(axis)
        if center is None:
            lo, hi = self.bounds()
            center = (lo[a] + hi[a]) / 2
        moved = {}
        for p, block in self.blocks.items():
            if p[a] < center:
                q = list(p)
                q[a] = round(2 * center - p[a])
                moved[tuple(q)] = mirror_state(block, axis)
        for q in [p for p in self.blocks if p[a] > center]:
            del self.blocks[q]
        for p, block in moved.items():
            self.put(p, block)
        return len(moved)

    # --- reading -------------------------------------------------------------------------------------------------

    def bounds(self) -> tuple[Pos, Pos]:
        if not self.blocks:
            return (0, 0, 0), (0, 0, 0)
        xs, ys, zs = zip(*self.blocks)
        return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

    def size(self) -> Pos:
        lo, hi = self.bounds()
        return (hi[0] - lo[0] + 1, hi[1] - lo[1] + 1, hi[2] - lo[2] + 1) if self.blocks else (0, 0, 0)

    def resolve(self, block: str) -> str:
        """The block state block builds as with this design's palette."""
        return PALETTES[self.palette][block[1:]] if block.startswith("@") else block

    def resolved(self) -> dict[Pos, str]:
        """The blocks moved so the lowest corner is 0, 0, 0, roles swapped for the palette's blocks."""
        lo, _ = self.bounds()
        return {(x - lo[0], y - lo[1], z - lo[2]): self.resolve(b) for (x, y, z), b in self.blocks.items()}

    def materials(self) -> dict:
        counts = Counter(self.resolve(b).split("[")[0] for b in self.blocks.values())
        tiers = {name: BLOCK_TIER.get(name, "unknown") for name in counts}
        known = [t for t in tiers.values() if t in TIERS]
        return {
            "palette": self.palette,
            "palette_tier": PALETTES[self.palette]["tier"],
            "highest_tier": max(known, key=TIERS.index) if known else "unknown",
            "total": sum(counts.values()),
            "blocks": [{"block": n, "count": c, "stacks": math.ceil(c / 64), "tier": tiers[n]}
                       for n, c in counts.most_common()],
        }
