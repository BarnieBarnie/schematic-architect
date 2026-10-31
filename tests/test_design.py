import pytest

from schematic_architect.design import Design, mirror_state, parse_block, turn_state


def test_parse_block_takes_roles_names_and_states():
    assert parse_block("primary") == "@primary"
    assert parse_block("oak_log") == "minecraft:oak_log"
    assert parse_block("minecraft:oak_stairs[facing=north,half=top]") == "minecraft:oak_stairs[facing=north,half=top]"
    assert parse_block("air") is None
    with pytest.raises(ValueError):
        parse_block("Oak Log!")


def test_box_modes():
    d = Design("t")
    assert d.box(0, 0, 0, 2, 2, 2, "@primary") == 27
    d = Design("t")
    assert d.box(0, 0, 0, 2, 2, 2, "@primary", "shell") == 26
    d = Design("t")
    assert d.box(0, 0, 0, 2, 2, 2, "@primary", "walls") == 24
    d = Design("t")
    assert d.box(0, 0, 0, 2, 2, 2, "@primary", "frame") == 20


def test_sphere_is_symmetric_and_a_dome_is_open_below():
    d = Design("t")
    d.sphere(0, 0, 0, 4, "@primary")
    assert all((-x, y, z) in d.blocks and (x, -y, z) in d.blocks for x, y, z in d.blocks)
    dome = Design("t")
    dome.sphere(0, 0, 0, 4, "@roof", hollow=True, half="top")
    assert min(y for _, y, _ in dome.blocks) == 0
    assert (0, 0, 0) not in dome.blocks  # the dome's floor is open, not capped
    assert (0, 4, 0) in dome.blocks


def test_cylinder_tube_is_open_at_the_ends():
    d = Design("t")
    d.cylinder(0, 0, 0, 3, 5, "@primary", hollow=True)
    assert (0, 0, 0) not in d.blocks and (3, 0, 0) in d.blocks
    assert d.size() == (7, 5, 7)


def test_pyramid_steps_in():
    d = Design("t")
    d.pyramid(0, 0, 4, 4, 0, "@roof")
    assert d.size() == (5, 3, 5)
    assert (2, 2, 2) in d.blocks and (0, 1, 0) not in d.blocks


def test_turn_and_mirror_states():
    assert turn_state("minecraft:oak_stairs[facing=north]", 1) == "minecraft:oak_stairs[facing=east]"
    assert turn_state("minecraft:oak_log[axis=x]", 1) == "minecraft:oak_log[axis=z]"
    assert mirror_state("minecraft:oak_stairs[facing=east]", "x") == "minecraft:oak_stairs[facing=west]"
    assert turn_state("@primary", 3) == "@primary"


def test_copy_turns_a_box_clockwise():
    d = Design("t")
    # An L: a row along +x at z=0 and one block at x=0, z=1.
    d.box(0, 0, 0, 2, 0, 0, "@primary")
    d.put((0, 0, 1), "@trim")
    d.copy(0, 0, 0, 2, 0, 1, 10, 0, 0, turns=1)
    # Turned clockwise (north to east), the row along +x runs along +z, at the high x of the 2-wide turned box.
    assert {(11, 0, 0), (11, 0, 1), (11, 0, 2)} <= set(d.blocks)
    assert d.blocks[(10, 0, 0)] == "@trim"


def test_symmetrize_mirrors_the_low_side():
    d = Design("t")
    d.box(0, 0, 0, 6, 0, 0, "@primary")
    d.put((1, 1, 0), "minecraft:oak_stairs[facing=east]")
    d.symmetrize("x")
    assert d.blocks[(5, 1, 0)] == "minecraft:oak_stairs[facing=west]"


def test_palette_swap_and_materials():
    d = Design("t", "oak")
    d.box(0, 0, 0, 1, 1, 1, "@primary")
    d.put((0, 2, 0), "minecraft:gold_block")
    assert d.resolve("@primary") == "minecraft:oak_log"
    m = d.materials()
    assert m["highest_tier"] == "late" and m["total"] == 9
    d.palette = "quartz"
    assert d.resolved()[(0, 0, 0)] == "minecraft:quartz_block"


def test_undo_and_replace():
    d = Design("t")
    d.checkpoint()
    d.box(0, 0, 0, 1, 0, 0, "minecraft:oak_log[axis=x]")
    assert d.replace("minecraft:oak_log", "minecraft:stone") == 2
    assert d.undo() and not d.blocks
