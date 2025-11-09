"""
Team name to Polymarket abbreviation mappings.

Provides functions to convert full team names (e.g., "Houston Rockets")
to Polymarket 3-letter abbreviations (e.g., "hou") for API calls.
"""

from backend.services.basketball_api import TEAM_ID_MAP as NBA_TEAM_ID_MAP
from backend.services.football_api import TEAM_ID_MAP as NFL_TEAM_ID_MAP


# Build reverse lookup dictionaries: Full Name -> Polymarket Abbreviation
NBA_NAME_TO_POLYMARKET = {
    full_name: poly_abbrev
    for _, (full_name, _, poly_abbrev) in NBA_TEAM_ID_MAP.items()
}

NFL_NAME_TO_POLYMARKET = {
    full_name: poly_abbrev
    for _, (full_name, _, poly_abbrev) in NFL_TEAM_ID_MAP.items()
}


def get_polymarket_abbrev(team_name: str, sport: str) -> str:
    """
    Convert full team name to Polymarket 3-letter abbreviation.

    Args:
        team_name: Full team name (e.g., "Houston Rockets", "Denver Broncos")
        sport: Sport type ("NBA" or "NFL")

    Returns:
        3-letter Polymarket abbreviation (e.g., "hou", "den")

    Raises:
        ValueError: If sport is not supported or team name not found

    Examples:
        >>> get_polymarket_abbrev("Houston Rockets", "NBA")
        "hou"
        >>> get_polymarket_abbrev("Denver Broncos", "NFL")
        "den"
        >>> get_polymarket_abbrev("Milwaukee Bucks", "NBA")
        "mil"
    """
    sport_upper = sport.upper()

    if sport_upper == "NBA":
        mapping = NBA_NAME_TO_POLYMARKET
    elif sport_upper == "NFL":
        mapping = NFL_NAME_TO_POLYMARKET
    else:
        raise ValueError(f"Unsupported sport: {sport}. Must be NBA or NFL.")

    if team_name not in mapping:
        raise ValueError(
            f"Team '{team_name}' not found in {sport} mappings. "
            f"Available teams: {sorted(mapping.keys())}"
        )

    return mapping[team_name]
