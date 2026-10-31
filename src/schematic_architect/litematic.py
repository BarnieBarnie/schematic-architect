"""Writes and reads Litematica schematics (.litematic): gzipped NBT with one region, block states packed into longs."""

import time
from pathlib import Path

from nbtlib import Compound, File, Int, List, Long, LongArray, String, load

from .design import Pos, join_state, split_state

# Minecraft 1.21.10: palette entries are written in Litematica's {Name, Properties} form, and the game brings a file
# of an older data version up to date when it loads it. Stamped with a newer version (26.3 is 5023) the game would take
# the old form as current and read every block as air.
DATA_VERSION = 4556
AIR = "minecraft:air"
# Empty positions are written as structure void: bots leave what stands there and can scaffold through it.
VOID = "minecraft:structure_void"


def _vec(x, y, z) -> Compound:
    return Compound({"x": Int(x), "y": Int(y), "z": Int(z)})


def _bits(entries: int) -> int:
    return max(2, (entries - 1).bit_length())


def pack(values: list[int], bits: int) -> list[int]:
    """values packed bits wide into 64-bit words, low bits first, an entry running on into the next word (Litematica's
    LitematicaBitArray), as signed longs."""
    words = [0] * ((len(values) * bits + 63) // 64)
    mask = (1 << 64) - 1
    for i, v in enumerate(values):
        start = i * bits
        word, offset = start >> 6, start & 63
        words[word] |= (v << offset) & mask
        if offset + bits > 64:
            words[word + 1] |= v >> (64 - offset)
    return [w - (1 << 64) if w >= 1 << 63 else w for w in words]


def unpack(words: list[int], bits: int, count: int) -> list[int]:
    big = [w & ((1 << 64) - 1) for w in words]
    out = []
    for i in range(count):
        start = i * bits
        word, offset = start >> 6, start & 63
        v = big[word] >> offset
        if offset + bits > 64:
            v |= big[word + 1] << (64 - offset)
        out.append(v & ((1 << bits) - 1))
    return out


def write(path: Path, name: str, blocks: dict[Pos, str], author: str = "schematic-architect", description: str = ""):
    """Writes blocks (lowest corner at 0, 0, 0) as a one-region schematic named name; the rest of the bounds is
    structure void."""
    sx, sy, sz = (max(p[i] for p in blocks) + 1 for i in range(3)) if blocks else (1, 1, 1)
    palette = [VOID] + sorted(set(blocks.values()))
    index = {state: i for i, state in enumerate(palette)}
    values = [0] * (sx * sy * sz)
    for (x, y, z), state in blocks.items():
        values[(y * sz + z) * sx + x] = index[state]
    now = Long(int(time.time() * 1000))
    states = List[Compound]()
    for state in palette:
        block, props = split_state(state)
        entry = Compound({"Name": String(block)})
        if props:
            entry["Properties"] = Compound({k: String(v) for k, v in props.items()})
        states.append(entry)
    region = Compound({
        "Position": _vec(0, 0, 0),
        "Size": _vec(sx, sy, sz),
        "BlockStatePalette": states,
        "BlockStates": LongArray(pack(values, _bits(len(palette)))),
        "TileEntities": List[Compound](),
        "Entities": List[Compound](),
        "PendingBlockTicks": List[Compound](),
        "PendingFluidTicks": List[Compound](),
    })
    root = Compound({
        "Version": Int(6),
        "SubVersion": Int(1),
        "MinecraftDataVersion": Int(DATA_VERSION),
        "Metadata": Compound({
            "Name": String(name),
            "Author": String(author),
            "Description": String(description),
            "RegionCount": Int(1),
            "TotalVolume": Int(sx * sy * sz),
            "TotalBlocks": Int(len(blocks)),
            "TimeCreated": now,
            "TimeModified": now,
            "EnclosingSize": _vec(sx, sy, sz),
        }),
        "Regions": Compound({name: region}),
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    File(root, gzipped=True).save(path)


def read(path: Path) -> tuple[str, dict[Pos, str]]:
    """The name and blocks of a schematic, its regions merged from their lowest corner (later regions win), air and structure void left out."""
    root = load(path, gzipped=True)
    name = str(root["Metadata"]["Name"])
    blocks: dict[Pos, str] = {}
    for region in root["Regions"].values():
        pos = [int(region["Position"][k]) for k in "xyz"]
        size = [int(region["Size"][k]) for k in "xyz"]
        lo = [p + s + 1 if s < 0 else p for p, s in zip(pos, size)]
        sx, sy, sz = (abs(s) for s in size)
        palette = [join_state(str(e["Name"]), {k: str(v) for k, v in e.get("Properties", {}).items()})
                   for e in region["BlockStatePalette"]]
        values = unpack([int(w) for w in region["BlockStates"]], _bits(len(palette)), sx * sy * sz)
        for i, v in enumerate(values):
            x, z, y = i % sx, (i // sx) % sz, i // (sx * sz)
            p = (lo[0] + x, lo[1] + y, lo[2] + z)
            if v < len(palette) and palette[v] not in (AIR, VOID, "minecraft:cave_air"):
                blocks[p] = palette[v]
            else:
                blocks.pop(p, None)
    if blocks:
        low = [min(p[i] for p in blocks) for i in range(3)]
        blocks = {(x - low[0], y - low[1], z - low[2]): b for (x, y, z), b in blocks.items()}
    return name, blocks
