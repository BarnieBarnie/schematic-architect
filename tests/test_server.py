import json

from schematic_architect import litematic, server


def test_giant_oak_cross_end_to_end(tmp_path):
    """The README's example: a cross from oak, previewed, costed, swapped to quartz and exported to a data pack."""
    server.new_design("cross", "oak")
    server.box("cross", 0, 0, 0, 2, 20, 2, "primary")
    server.box("cross", -5, 13, 0, 7, 15, 2, "primary")
    server.box("cross", -5, 14, 0, 7, 14, 2, "trim")
    assert server.preview("cross").data[:8] == b"\x89PNG\r\n\x1a\n"
    assert server.preview("cross", "layer", 14).data[:4] == b"\x89PNG"
    assert "minecraft:stripped_oak_log" in server.layer("cross", 14)
    m = json.loads(server.materials("cross"))
    # The post (3x21x3) and the arms (13x3x3) less where they overlap (3x3x3).
    assert m["palette_tier"] == "early" and m["total"] == 189 + 117 - 27

    server.set_palette("cross", "quartz")
    out = server.export("cross", str(tmp_path / "pack"))
    path = tmp_path / "pack" / "data" / "architect" / "blueprint" / "cross.litematic"
    assert str(path) in out
    assert json.loads((tmp_path / "pack" / "pack.mcmeta").read_text())["pack"]["min_format"] == server.PACK_FORMAT
    _, blocks = litematic.read(path)
    assert set(blocks.values()) == {"minecraft:quartz_block", "minecraft:quartz_pillar"}


def test_open_schematic_and_undo(tmp_path):
    server.new_design("hut", "cobble")
    server.box("hut", 0, 0, 0, 4, 3, 4, "primary", "shell")
    server.export("hut", str(tmp_path / "hut.litematic"))
    server.open_schematic(str(tmp_path / "hut.litematic"), "hut2")
    assert len(server.designs["hut2"].blocks) == len(server.designs["hut"].blocks)
    server.clear("hut2", 0, 0, 0, 4, 3, 4)
    server.undo("hut2")
    assert server.designs["hut2"].blocks
