"""The MCP server: tools an agent calls to design a schematic from a player's prompt, look at it, and export it."""

import json
import re
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer

from . import litematic, render
from .design import Design, parse_block
from .palettes import PALETTES, ROLES

PACK_FORMAT = 121  # Minecraft 26.3 data packs
_NAME = re.compile(r"^[a-z0-9_.-]+$")

INSTRUCTIONS = f"""Design Minecraft builds block by block and export them as .litematic schematics.

Workflow: new_design, then shapes (box, line, cylinder, sphere, pyramid, set_block), editing (clear, replace, copy,
symmetrize, undo), check your work with preview (an image) or layer (text), check cost with materials, then export.

Coordinates: integers, y is up, x east, z south. Shapes take inclusive corners. Positions can be anywhere: the export
moves the lowest corner to 0, 0, 0. Every position inside the bounds with no block is air, and a bot building the
schematic clears what stands there, so keep a build compact.

Blocks: paint with a palette role ({', '.join(ROLES)}) so the player can swap the palette later (early game oak,
late game quartz), or name a block ("oak_log", "minecraft:oak_stairs[facing=north]") where a role does not fit.
"air" removes blocks. Palettes have a tier: early, mid or late. Pick one that fits the player's stage; ask if unsure.

Preview after each big step and fix what looks wrong. Big builds: the in-game ghost shows at most 4096 blocks."""

mcp = MCPServer("schematic-architect", instructions=INSTRUCTIONS)
designs: dict[str, Design] = {}


def _get(design: str) -> Design:
    if design not in designs:
        raise ValueError(f"no design {design!r}; designs: {', '.join(designs) or 'none'} (start one with new_design)")
    return designs[design]


def _edit(design: str, change) -> str:
    d = _get(design)
    d.checkpoint()
    n = change(d)
    sx, sy, sz = d.size()
    return f"{n} positions changed; {design} now has {len(d.blocks)} blocks in {sx}x{sy}x{sz} (x, y, z)"


@mcp.tool()
def palettes() -> str:
    """The palettes, by tier, with the block each role builds as."""
    return json.dumps(PALETTES, indent=1)


@mcp.tool()
def new_design(design: str, palette: str = "oak") -> str:
    """Starts an empty design named design (lowercase letters, digits, _ . -; it becomes the blueprint id) with a palette."""
    if not _NAME.match(design):
        raise ValueError("a design name takes lowercase letters, digits, _, . and - only")
    designs[design] = Design(design, palette)
    return f"started {design} with palette {palette} ({PALETTES[palette]['tier']} game)"


@mcp.tool()
def list_designs() -> str:
    """The designs open in this session, with their palette, size and block count."""
    return "\n".join(f"{n}: palette {d.palette}, {len(d.blocks)} blocks, size {d.size()}" for n, d in designs.items()) \
        or "no designs"


@mcp.tool()
def open_schematic(path: str, design: str | None = None) -> str:
    """Opens a .litematic file as a design to change, its blocks as they are (no roles)."""
    name, blocks = litematic.read(Path(path).expanduser())
    design = design or re.sub(r"[^a-z0-9_.-]", "_", Path(path).stem.lower())
    d = Design(design)
    d.blocks = blocks
    designs[design] = d
    return f"opened {name} as {design}: {len(blocks)} blocks, size {d.size()}"


@mcp.tool()
def set_palette(design: str, palette: str) -> str:
    """Builds the design's roles from another palette, such as a late-game one; literal blocks stay as they are."""
    d = _get(design)
    if palette not in PALETTES:
        raise ValueError(f"no palette {palette!r}; palettes: {', '.join(PALETTES)}")
    d.palette = palette
    return f"{design} now uses {palette} ({PALETTES[palette]['tier']} game)"


@mcp.tool()
def set_block(design: str, x: int, y: int, z: int, block: str) -> str:
    """Puts one block (a role, a block state, or air)."""
    return _edit(design, lambda d: d.put((x, y, z), parse_block(block)) or 1)


@mcp.tool()
def box(design: str, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, block: str, mode: str = "solid") -> str:
    """Fills a box between two corners: mode solid, shell (six faces, hollow inside), walls (four sides, no floor or
    roof) or frame (the twelve edges)."""
    return _edit(design, lambda d: d.box(x1, y1, z1, x2, y2, z2, parse_block(block), mode))


@mcp.tool()
def line(design: str, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, block: str) -> str:
    """A one-block line between two points, diagonal too."""
    return _edit(design, lambda d: d.line(x1, y1, z1, x2, y2, z2, parse_block(block)))


@mcp.tool()
def cylinder(design: str, x: int, y: int, z: int, radius: int, length: int, block: str, axis: str = "y",
             hollow: bool = False) -> str:
    """A cylinder whose first end is centred on x, y, z, running length blocks along +axis (y: a tower, x or z: a
    tunnel or arch). hollow leaves a tube open at both ends."""
    return _edit(design, lambda d: d.cylinder(x, y, z, radius, length, parse_block(block), axis, hollow))


@mcp.tool()
def sphere(design: str, x: int, y: int, z: int, radius: int, block: str, hollow: bool = False,
           half: str | None = None) -> str:
    """A ball centred on x, y, z. half "top" keeps the upper half (a dome), "bottom" the lower (a bowl)."""
    return _edit(design, lambda d: d.sphere(x, y, z, radius, parse_block(block), hollow, half))


@mcp.tool()
def pyramid(design: str, x1: int, z1: int, x2: int, z2: int, y: int, block: str, hollow: bool = False) -> str:
    """A stepped pyramid on the rectangle x1..x2, z1..z2 starting at height y, one smaller on every side each layer up.
    Also good for a stepped roof."""
    return _edit(design, lambda d: d.pyramid(x1, z1, x2, z2, y, parse_block(block), hollow))


@mcp.tool()
def clear(design: str, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int) -> str:
    """Removes every block in a box (doors, windows, hollowing out)."""
    return _edit(design, lambda d: d.clear(x1, y1, z1, x2, y2, z2))


@mcp.tool()
def replace(design: str, old: str, new: str) -> str:
    """Swaps every old block or role for new; a block name without state matches all its states."""
    return _edit(design, lambda d: d.replace(parse_block(old), parse_block(new)))


@mcp.tool()
def copy(design: str, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, dx: int, dy: int, dz: int,
         turns: int = 0, mirror: str | None = None) -> str:
    """Copies the blocks of a box dx, dy, dz on (repeat a window, a pillar, a wing), mirrored ("x" or "z") and turned
    a quarter clockwise (seen from above) turns times within the box. Facing and axis states turn with them."""
    return _edit(design, lambda d: d.copy(x1, y1, z1, x2, y2, z2, dx, dy, dz, turns, mirror))


@mcp.tool()
def symmetrize(design: str, axis: str, center: float | None = None) -> str:
    """Makes the design symmetric across a plane: the low side (smaller x or z) is mirrored onto the high side.
    center is the plane's x or z; the middle of the design by default."""
    return _edit(design, lambda d: d.symmetrize(axis, center))


@mcp.tool()
def undo(design: str) -> str:
    """Takes back the last change (up to 20)."""
    d = _get(design)
    return f"undone; {len(d.blocks)} blocks" if d.undo() else "nothing to undo"


@mcp.tool()
def materials(design: str) -> str:
    """What the design takes to build: blocks with counts, stacks and tier, and the highest tier it needs."""
    return json.dumps(_get(design).materials(), indent=1)


@mcp.tool()
def preview(design: str, view: str = "all", y: int | None = None) -> Image:
    """A picture of the design: "all" (isometric beside top, front and side), "iso", "top", "front" (from the south),
    "side" (from the east), or "layer" with y (one height, from above, y counted from the bottom of the design).
    Colours are guessed from block names; glass is see-through."""
    blocks = _get(design).resolved()
    if view == "all":
        image = render.sheet(blocks)
    elif view == "iso":
        image = render.iso(blocks)
    elif view in ("top", "front", "side"):
        image = render.flat(blocks, view)
    elif view == "layer":
        image = render.layer(blocks, y or 0)
    else:
        raise ValueError("view is all, iso, top, front, side or layer")
    return Image(data=render.png(image), format="png")


@mcp.tool()
def layer(design: str, y: int) -> str:
    """One height of the design as text, from above (north up, x to the right), y counted from the bottom; a letter
    a block, "." air. For checking exact positions."""
    d = _get(design)
    blocks = d.resolved()
    sx, _, sz = d.size()
    keys: dict[str, str] = {}
    rows = []
    for z in range(sz):
        row = ""
        for x in range(sx):
            b = blocks.get((x, y, z))
            if b is None:
                row += "."
                continue
            keys.setdefault(b, "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"[len(keys) % 62])
            row += keys[b]
        rows.append(row)
    return "\n".join(rows) + "\n\n" + "\n".join(f"{k} = {b}" for b, k in keys.items())


@mcp.tool()
def export(design: str, datapack: str, namespace: str = "architect", description: str = "") -> str:
    """Writes the design as data/<namespace>/blueprint/<design>.litematic in a data pack folder, such as
    <world>/datapacks/architect, making the pack's pack.mcmeta if it has none. After /reload in game it is blueprint
    <namespace>:<design>: pick it with the Blueprint item, and bots build it with build("<namespace>:<design>", at).
    A path ending in .litematic writes just that file instead."""
    d = _get(design)
    if not d.blocks:
        raise ValueError(f"{design} is empty")
    if not _NAME.match(namespace):
        raise ValueError("a namespace takes lowercase letters, digits, _, . and - only")
    target = Path(datapack).expanduser()
    if target.suffix == ".litematic":
        path = target
    else:
        path = target / "data" / namespace / "blueprint" / f"{design}.litematic"
        mcmeta = target / "pack.mcmeta"
        if not mcmeta.exists():
            target.mkdir(parents=True, exist_ok=True)
            mcmeta.write_text(json.dumps({"pack": {"description": "Schematics from schematic-architect",
                                                   "min_format": PACK_FORMAT, "max_format": PACK_FORMAT}}, indent=2))
    litematic.write(path, design, d.resolved(), description=description)
    sx, sy, sz = d.size()
    note = " The in-game ghost shows only 4096 of its blocks." if len(d.blocks) > 4096 else ""
    return f"wrote {path} ({len(d.blocks)} blocks, {sx}x{sy}x{sz}, palette {d.palette}).{note}"


def main():
    mcp.run()


if __name__ == "__main__":
    main()
