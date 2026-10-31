"""Material palettes: the block each role builds as, by game stage (palettes.toml)."""

import tomllib
from importlib.resources import files

ROLES = ("primary", "secondary", "trim", "accent", "glass", "roof", "floor", "light")
TIERS = ("early", "mid", "late")

PALETTES: dict[str, dict] = tomllib.loads(files(__package__).joinpath("palettes.toml").read_text())

for _name, _palette in PALETTES.items():
    missing = [role for role in ROLES if role not in _palette]
    assert not missing and _palette["tier"] in TIERS, f"palette {_name}: missing {missing} or bad tier"

# The earliest tier a block appears in any palette, so literal blocks get a tier too.
BLOCK_TIER: dict[str, str] = {}
for _palette in sorted(PALETTES.values(), key=lambda p: TIERS.index(p["tier"]), reverse=True):
    for _role in ROLES:
        BLOCK_TIER[_palette[_role].split("[")[0]] = _palette["tier"]


def block_for(palette: str, role: str) -> str:
    return PALETTES[palette][role]
