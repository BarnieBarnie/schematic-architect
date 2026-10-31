"""Pictures of a design for the agent to check its work: an isometric view, top, front and side views, and layers.

Blocks are flat colours guessed from their names, not game textures."""

import hashlib
import io

from PIL import Image, ImageDraw

from .design import Pos

# Exact colours for common blocks; the rest go by the words in their name (KEYWORDS), then by a hash.
COLOURS = {
    "oak_log": (109, 85, 50), "oak_planks": (162, 130, 78), "stripped_oak_log": (177, 144, 86),
    "spruce_log": (58, 37, 16), "spruce_planks": (114, 84, 48), "stripped_spruce_log": (115, 89, 52),
    "birch_log": (216, 215, 210), "birch_planks": (192, 175, 121), "stripped_birch_log": (196, 176, 118),
    "dark_oak_planks": (66, 43, 20), "dark_oak_log": (60, 46, 26), "jungle_planks": (160, 115, 80),
    "acacia_planks": (168, 90, 50), "mangrove_planks": (117, 54, 48), "cherry_planks": (226, 178, 172),
    "crimson_planks": (101, 48, 70), "warped_planks": (43, 104, 99), "bamboo_planks": (193, 173, 80),
    "cobblestone": (127, 127, 127), "mossy_cobblestone": (110, 118, 94), "stone": (125, 125, 125),
    "smooth_stone": (158, 158, 158), "stone_bricks": (122, 121, 122), "mossy_stone_bricks": (115, 121, 105),
    "chiseled_stone_bricks": (119, 118, 119), "andesite": (136, 136, 136), "polished_andesite": (132, 134, 133),
    "diorite": (188, 188, 188), "polished_diorite": (192, 193, 194), "granite": (149, 103, 85),
    "sandstone": (216, 203, 155), "smooth_sandstone": (223, 214, 170), "cut_sandstone": (217, 206, 159),
    "chiseled_sandstone": (216, 202, 154), "red_sandstone": (186, 99, 29), "sand": (219, 207, 163),
    "bricks": (150, 97, 83), "terracotta": (152, 94, 67), "mud_bricks": (137, 103, 79),
    "deepslate": (80, 80, 82), "deepslate_bricks": (70, 70, 71), "deepslate_tiles": (54, 54, 55),
    "polished_deepslate": (72, 72, 73), "chiseled_deepslate": (54, 54, 54), "cobbled_deepslate": (77, 77, 80),
    "copper_block": (192, 107, 79), "cut_copper": (191, 106, 80), "chiseled_copper": (184, 100, 73),
    "exposed_cut_copper": (155, 122, 101), "weathered_cut_copper": (109, 145, 107),
    "oxidized_cut_copper": (79, 153, 126), "quartz_block": (235, 229, 222), "smooth_quartz": (236, 230, 223),
    "quartz_pillar": (235, 230, 224), "quartz_bricks": (234, 229, 221), "chiseled_quartz_block": (231, 226, 218),
    "gold_block": (246, 208, 61), "iron_block": (220, 220, 220), "diamond_block": (98, 237, 228),
    "emerald_block": (42, 203, 87), "lapis_block": (30, 67, 140), "redstone_block": (175, 24, 5),
    "netherite_block": (66, 61, 63), "amethyst_block": (133, 97, 191), "obsidian": (15, 10, 24),
    "crying_obsidian": (32, 10, 60), "polished_blackstone_bricks": (48, 42, 49), "polished_blackstone": (53, 48, 56),
    "chiseled_polished_blackstone": (53, 48, 56), "gilded_blackstone": (56, 43, 38), "blackstone": (42, 36, 41),
    "polished_basalt": (99, 98, 100), "basalt": (80, 81, 86), "netherrack": (97, 38, 38), "nether_bricks": (44, 21, 26),
    "red_nether_bricks": (69, 7, 9), "shroomlight": (240, 146, 70), "glowstone": (171, 131, 84),
    "prismarine": (99, 156, 151), "prismarine_bricks": (99, 171, 158), "dark_prismarine": (51, 91, 75),
    "sea_lantern": (172, 199, 190), "purpur_block": (169, 125, 169), "purpur_pillar": (171, 129, 171),
    "end_stone": (219, 222, 158), "end_stone_bricks": (218, 224, 162), "end_rod": (230, 224, 214),
    "glass": (200, 225, 235), "tinted_glass": (44, 38, 46), "torch": (255, 200, 80), "lantern": (106, 91, 83),
    "grass_block": (127, 178, 56), "dirt": (134, 96, 67), "gravel": (131, 127, 126), "snow_block": (249, 254, 254),
    "ice": (145, 183, 253), "packed_ice": (141, 180, 250), "water": (63, 118, 228), "lava": (207, 91, 20),
    "hay_block": (166, 136, 38), "bookshelf": (117, 94, 60), "white_wool": (234, 236, 237), "clay": (160, 166, 179),
}
DYES = {
    "white": (234, 236, 237), "orange": (241, 118, 20), "magenta": (190, 69, 180), "light_blue": (58, 175, 217),
    "yellow": (249, 198, 40), "lime": (112, 185, 26), "pink": (238, 141, 172), "gray": (63, 68, 72),
    "light_gray": (142, 142, 135), "cyan": (21, 138, 145), "purple": (122, 42, 173), "blue": (53, 57, 157),
    "brown": (114, 72, 41), "green": (85, 110, 28), "red": (161, 39, 35), "black": (21, 21, 26),
}
KEYWORDS = [
    ("dark_oak", (66, 43, 20)), ("oak", (162, 130, 78)), ("spruce", (114, 84, 48)), ("birch", (192, 175, 121)),
    ("jungle", (160, 115, 80)), ("acacia", (168, 90, 50)), ("mangrove", (117, 54, 48)), ("cherry", (226, 178, 172)),
    ("crimson", (101, 48, 70)), ("warped", (43, 104, 99)), ("bamboo", (193, 173, 80)), ("deepslate", (70, 70, 71)),
    ("blackstone", (48, 42, 49)), ("cobblestone", (127, 127, 127)), ("red_sandstone", (186, 99, 29)),
    ("sandstone", (216, 203, 155)), ("quartz", (235, 229, 222)), ("prismarine", (99, 171, 158)),
    ("purpur", (169, 125, 169)), ("end_stone", (218, 224, 162)), ("nether_brick", (44, 21, 26)),
    ("brick", (150, 97, 83)), ("oxidized", (79, 153, 126)), ("weathered", (109, 145, 107)),
    ("exposed", (155, 122, 101)), ("copper", (191, 106, 80)), ("andesite", (132, 134, 133)),
    ("diorite", (192, 193, 194)), ("granite", (149, 103, 85)), ("tuff", (108, 109, 102)), ("mud", (137, 103, 79)),
    ("stone", (125, 125, 125)), ("glass", (200, 225, 235)), ("leaves", (60, 110, 40)), ("gold", (246, 208, 61)),
    ("iron", (220, 220, 220)), ("lantern", (106, 91, 83)), ("torch", (255, 200, 80)),
]
GLASS_ALPHA = 140
BACKGROUND = (246, 246, 242, 255)


def colour(block: str) -> tuple[int, int, int, int]:
    name = block.split("[")[0].split(":")[-1]
    alpha = GLASS_ALPHA if "glass" in name else 255
    if name in COLOURS:
        return (*COLOURS[name], alpha)
    for dye, rgb in DYES.items():
        if name.startswith(dye + "_"):
            return (*rgb, alpha)
    for word, rgb in KEYWORDS:
        if word in name:
            return (*rgb, alpha)
    h = hashlib.md5(name.encode()).digest()
    return (h[0], h[1], h[2], alpha)


def _shade(c, f):
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f), c[3])


def png(image: Image.Image) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def iso(blocks: dict[Pos, str], max_px: int = 900) -> Image.Image:
    """The design seen from above the south-east corner: tops, south faces and east faces of the blocks that show."""
    if not blocks:
        return Image.new("RGBA", (64, 64), BACKGROUND)
    sx, sy, sz = (max(p[i] for p in blocks) + 1 for i in range(3))
    # A cube is 2t wide; its top is a diamond t tall, its sides 2t tall.
    t = max(1, min(24, int(max_px / (sx + sz + 2)), int(max_px / ((sx + sz) / 2 + sy * 2 + 2))))
    w = (sx + sz) * t + 2 * t
    h = int((sx + sz) * t / 2 + sy * 2 * t + 2 * t)
    ox, oy = sz * t + t, sy * 2 * t + t

    def pt(x, y, z):
        return (ox + (x - z) * t, oy + (x + z) * t / 2 - y * 2 * t)

    image = Image.new("RGBA", (w, h), BACKGROUND)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    edge = t >= 6
    # Far to near: the screen looks along (-2, -1, -2), so nearer blocks have a larger 2x + y + 2z.
    for (x, y, z) in sorted(blocks, key=lambda p: 2 * p[0] + p[1] + 2 * p[2]):
        c = colour(blocks[(x, y, z)])
        faces = []
        if (x, y + 1, z) not in blocks:
            faces.append(([pt(x, y + 1, z), pt(x + 1, y + 1, z), pt(x + 1, y + 1, z + 1), pt(x, y + 1, z + 1)], 1.0))
        if (x, y, z + 1) not in blocks:
            faces.append(([pt(x, y, z + 1), pt(x + 1, y, z + 1), pt(x + 1, y + 1, z + 1), pt(x, y + 1, z + 1)], 0.68))
        if (x + 1, y, z) not in blocks:
            faces.append(([pt(x + 1, y, z), pt(x + 1, y, z + 1), pt(x + 1, y + 1, z + 1), pt(x + 1, y + 1, z)], 0.84))
        for poly, f in faces:
            draw.polygon(poly, fill=_shade(c, f), outline=_shade(c, f * 0.75) if edge else None)
        if c[3] < 255:
            # Glass shows what is behind it: blend this layer in now and start a fresh one.
            image.alpha_composite(layer)
            layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(layer)
    image.alpha_composite(layer)
    return image


def _grid(cells: dict[tuple[int, int], tuple], cols: int, rows: int, cell: int) -> Image.Image:
    image = Image.new("RGBA", (cols * cell + 1, rows * cell + 1), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for (c, r), fill in cells.items():
        draw.rectangle([c * cell, r * cell, (c + 1) * cell, (r + 1) * cell], fill=fill,
                       outline=(200, 200, 196, 255) if cell >= 6 else None)
    return image


def flat(blocks: dict[Pos, str], view: str, max_px: int = 600) -> Image.Image:
    """The nearest block of each column: top (from above, north up), front (from the south), side (from the east)."""
    if not blocks:
        return Image.new("RGBA", (64, 64), BACKGROUND)
    sx, sy, sz = (max(p[i] for p in blocks) + 1 for i in range(3))
    # Each view: the screen column and row of a block, its depth (larger is nearer), and the size of the screen.
    axes = {
        "top": (lambda x, y, z: (x, z, y), sx, sz, sy),
        "front": (lambda x, y, z: (x, sy - 1 - y, z), sx, sy, sz),
        "side": (lambda x, y, z: (sz - 1 - z, sy - 1 - y, x), sz, sy, sx),
    }
    to_screen, cols, rows, depth = axes[view]
    nearest: dict[tuple[int, int], tuple[int, str]] = {}
    for p, b in blocks.items():
        c, r, d = to_screen(*p)
        if (c, r) not in nearest or d > nearest[(c, r)][0]:
            nearest[(c, r)] = (d, b)
    cell = max(1, min(24, max_px // max(cols, rows)))
    # Farther blocks are drawn darker, so depth shows.
    cells = {k: _shade(colour(b), 0.55 + 0.45 * (d + 1) / depth) for k, (d, b) in nearest.items()}
    return _grid(cells, cols, rows, cell)


def layer(blocks: dict[Pos, str], y: int, max_px: int = 600) -> Image.Image:
    """The blocks at height y, seen from above (north up)."""
    sx = max((p[0] for p in blocks), default=0) + 1
    sz = max((p[2] for p in blocks), default=0) + 1
    cell = max(1, min(24, max_px // max(sx, sz)))
    return _grid({(x, z): colour(b) for (x, yy, z), b in blocks.items() if yy == y}, sx, sz, cell)


def sheet(blocks: dict[Pos, str]) -> Image.Image:
    """The isometric view beside the top, front and side views, on one image."""
    views = [iso(blocks, 700), flat(blocks, "top", 340), flat(blocks, "front", 340), flat(blocks, "side", 340)]
    pad = 12
    right_w = max(v.width for v in views[1:])
    w = views[0].width + right_w + pad * 3
    h = max(views[0].height, sum(v.height for v in views[1:]) + pad * 2) + pad * 2
    image = Image.new("RGBA", (w, h), BACKGROUND)
    image.alpha_composite(views[0], (pad, pad))
    y = pad
    for v in views[1:]:
        image.alpha_composite(v, (views[0].width + pad * 2, y))
        y += v.height + pad
    return image
