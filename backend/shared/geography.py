"""
Geographic hierarchy for region normalisation.

Maps sub-regional names (snake_case) to their parent canonical region.
Used by the client matcher to prevent geographic over-match and to handle
events reported with sub-regional granularity.
"""

from __future__ import annotations

GEO_HIERARCHY: dict[str, str] = {
    "eastern_europe": "europe",
    "western_europe": "europe",
    "northern_europe": "europe",
    "southern_europe": "europe",
    "southeast_asia": "asia_pacific",
    "east_asia": "asia_pacific",
    "south_asia": "asia_pacific",
    "oceania": "asia_pacific",
    "north_africa": "africa",
    "sub_saharan_africa": "africa",
    "west_africa": "africa",
    "east_africa": "africa",
    "gulf": "middle_east",
    "levant": "middle_east",
    "latin_america": "north_america",  # coarse mapping for PoC
    "south_america": "north_america",
    "central_america": "north_america",
    "caribbean": "north_america",
}


def normalise_geography(region: str) -> str:
    """
    Map a sub-regional name to its parent canonical region.

    Accepts any casing or separator style and converts to snake_case
    before lookup.  Returns the input slug unchanged if not found in
    the hierarchy (allowing exact matches to still work).
    """
    slug = region.lower().replace(" ", "_").replace("-", "_")
    return GEO_HIERARCHY.get(slug, slug)
