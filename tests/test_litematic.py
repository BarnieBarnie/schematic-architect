import litemapy

from schematic_architect import litematic
from schematic_architect.design import Design


def _design():
    d = Design("tower", "stone_brick")
    d.cylinder(0, 0, 0, 4, 10, "@primary", hollow=True)
    d.sphere(0, 10, 0, 4, "@roof", hollow=True, half="top")
    d.put((0, 1, 4), "minecraft:oak_door[facing=south,half=lower]")
    d.put((0, 2, 4), "minecraft:oak_door[facing=south,half=upper]")
    d.put((-3, 5, 0), "@glass")
    # Over four palette entries, so entries are 3 bits wide and some run over a long's end.
    for i, b in enumerate(["red_wool", "blue_wool", "lime_wool", "white_wool", "black_wool"]):
        d.put((i, 15, 0), "minecraft:" + b)
    return d


def test_round_trip(tmp_path):
    d = _design()
    path = tmp_path / "tower.litematic"
    litematic.write(path, "tower", d.resolved())
    name, blocks = litematic.read(path)
    assert name == "tower"
    assert blocks == d.resolved()


def test_pack_runs_entries_over_word_ends():
    values = [i % 7 for i in range(500)]
    assert litematic.unpack(litematic.pack(values, 3), 3, 500) == values
    assert all(-(1 << 63) <= w < 1 << 63 for w in litematic.pack([1] * 100, 5))


def test_litemapy_reads_it(tmp_path):
    """An independent reader agrees, so Litematica (and AntCraft, which packs as it does) read the file."""
    d = _design()
    path = tmp_path / "tower.litematic"
    litematic.write(path, "tower", d.resolved())
    schematic = litemapy.Schematic.load(str(path))
    region = next(iter(schematic.regions.values()))
    want = d.resolved()
    seen = {}
    for x, y, z in region.block_positions():
        state = region[x, y, z]
        if state.id != "minecraft:air":
            props = ",".join(f"{k}={v}" for k, v in sorted(state.properties()))
            seen[(x, y, z)] = state.id + (f"[{props}]" if props else "")
    norm = {p: b.split("[")[0] + ("[" + ",".join(sorted(b[b.index("[") + 1:-1].split(","))) + "]" if "[" in b else "")
            for p, b in want.items()}
    assert seen == norm
