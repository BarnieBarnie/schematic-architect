# schematic-architect

An [MCP](https://modelcontextprotocol.io) server that lets an AI agent design Minecraft builds from a player's prompt
("make a giant cross from oak") and export them as Litematica schematics (`.litematic`).

It was made for [AntCraft](https://github.com/BarnieBarnie/antcraft), whose bots build any `.litematic` in a data pack,
but the files work with Litematica too.

## How it works

The agent never places blocks one by one. It draws with shapes (`box`, `line`, `cylinder`, `sphere`, `pyramid`), edits
(`clear`, `replace`, `copy`, `symmetrize`, `undo`), looks at what it made (`preview` returns a picture, `layer` a text
grid), checks the cost (`materials`) and exports.

Blocks are painted with **palette roles** (`primary`, `secondary`, `trim`, `accent`, `glass`, `roof`, `floor`,
`light`) or with plain block states (`oak_log`, `minecraft:oak_stairs[facing=north]`). A palette names the block each
role builds as, so one design is built from oak early in the game and from quartz later:

| Tier | Palettes |
|---|---|
| early | `oak`, `spruce`, `birch`, `cobble`, `sandstone` |
| mid | `stone_brick`, `brick`, `deepslate`, `copper` |
| late | `quartz`, `blackstone`, `prismarine`, `purpur` |

The palettes live in [`palettes.toml`](src/schematic_architect/palettes.toml).

## Install

With [uv](https://docs.astral.sh/uv/), add it to your MCP client. For Claude Code:

```sh
claude mcp add schematic-architect -- uvx --from git+https://github.com/BarnieBarnie/schematic-architect schematic-architect
```

For Claude Desktop, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "schematic-architect": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/BarnieBarnie/schematic-architect", "schematic-architect"]
    }
  }
}
```

## Use it

Ask the agent, naming the world's data pack folder:

> Design a giant cross from oak and export it to `~/.minecraft/saves/MyWorld/datapacks/architect`.

The agent writes `datapacks/architect/data/architect/blueprint/cross.litematic` (and a `pack.mcmeta` if the pack has
none). In game, run `/reload`. With AntCraft the build is now blueprint `architect:cross`: pick it with the Blueprint
item to see its ghost, and a bot builds it with `build("architect:cross", at)`.

Later in the game: "rebuild the cross in quartz" swaps the palette with `set_palette` and exports again.

`open_schematic` loads an existing `.litematic` to change it.

## Good to know

- Every position inside the build's bounds that holds no block is **structure void**: a bot building it leaves what
  stands there and can put scaffolding through it. A hollow dome built into a hill is not dug out inside.
- AntCraft's ghost shows at most 4096 blocks of a build; bots build all of it.
- Block names are not checked against the game: a misspelt block becomes air when the game loads the file.
- Turning and mirroring (`copy`, `symmetrize`) turn `facing`, `axis` and sign `rotation`; stair corner shapes and fences
  keep their sides.
- The previews use flat colours guessed from block names, not the game's textures.
- Designs live in the server's memory for the session; export to keep them.

## Develop

```sh
uv sync
uv run pytest
```

The tests read every exported file back, and also with [litemapy](https://github.com/SmylerMC/litemapy), an
independent reader, so the files load in Litematica and AntCraft.
