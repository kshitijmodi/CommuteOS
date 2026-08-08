from app.station_index import (
    contains_whole,
    find_stations,
    nearest_stations,
    normalize,
    station_for,
)


def test_contains_whole_matches_a_name_inside_a_full_sentence():
    assert contains_whole("what do i usually take from grove street", "grove street")


def test_contains_whole_does_not_match_a_fragment_inside_an_unrelated_word():
    assert not contains_whole("what does average commute look like", "ave")


def test_contains_whole_returns_false_for_an_empty_needle():
    assert not contains_whole("anything", "")


def test_normalize_strips_punctuation_and_lowercases():
    assert normalize("Grove Street!") == "grove street"
    assert normalize("33 St") == "33 st"


def test_find_stations_matches_a_real_station_by_exact_name():
    matches = find_stations("Hoboken")

    assert len(matches) > 0
    assert any(m.agency == "path" and m.code == "HOB" for m in matches)


def test_find_stations_is_case_and_punctuation_insensitive():
    matches = find_stations("  HOBOKEN  ")

    assert any(m.agency == "path" for m in matches)


def test_find_stations_matches_a_station_name_embedded_in_a_full_question():
    # Real chat questions are full sentences, not bare station names - the
    # station name is a substring OF the question, never the reverse.
    matches = find_stations("what time is the next PATH train from Grove Street")

    assert any(m.agency == "path" and m.code == "GRV" for m in matches)


def test_find_stations_does_not_match_a_short_name_inside_an_unrelated_word():
    # A short/common word that happens to be a station name shouldn't
    # match every question containing it as a word-fragment.
    matches = find_stations("what does average commute time look like")

    assert not any(normalize(m.name) == "ave" for m in matches)


def test_find_stations_returns_empty_for_nonsense_query():
    assert find_stations("this is not a real station name xyz123") == []


def test_find_stations_returns_empty_for_blank_query():
    assert find_stations("") == []
    assert find_stations("   ") == []


def test_find_stations_respects_limit():
    matches = find_stations("st", limit=3)

    assert len(matches) <= 3


def test_find_stations_ranks_shorter_names_first():
    matches = find_stations("Hoboken", limit=10)

    # The real "Hoboken" station name is shorter than any "Hoboken Ave at
    # ..." NJT bus stop name that also substring-matches - it should rank
    # first.
    assert matches[0].name == "Hoboken"


def test_mta_and_path_stations_carry_their_real_route_or_direction_candidates():
    matches = find_stations("Journal Square")
    path_match = next(m for m in matches if m.agency == "path")

    # PATH rows carry its two fixed direction keys (see
    # build_chat_station_index.py's _path_rows) - Commute AI reads this
    # as the station's real candidate set, same as MTA's routes below.
    assert path_match.routes == ["ToNY", "ToNJ"]

    mta_matches = [m for m in find_stations("Astoria Blvd") if m.agency == "mta"]
    assert mta_matches
    assert mta_matches[0].routes  # real MTA rows have at least one route


def test_njt_rail_stations_carry_no_route_candidates():
    # NJT rail/bus/LIRR need no route_or_direction to fetch arrivals (a
    # station code alone returns every line) - unlike MTA/PATH, so these
    # correctly carry an empty candidate list, not a guessed one.
    matches = [m for m in find_stations("Newark Penn Station") if m.agency == "njt_rail"]

    assert matches
    assert matches[0].routes == []


def test_station_for_exact_agency_and_code_lookup():
    station = station_for("path", "JSQ")

    assert station is not None
    assert station.name == "Journal Square"
    assert station.routes == ["ToNY", "ToNJ"]


def test_station_for_returns_none_for_unknown_pair():
    assert station_for("mta", "NOT_A_REAL_STOP_ID") is None
    assert station_for("not_a_real_agency", "JSQ") is None


def test_njt_bus_stops_carry_a_real_toward_hint_when_one_exists():
    # Real stop_ids 15652/15653 are both named "PATH STATION" but are
    # genuinely different stops (opposite sides of a real intersection) -
    # their toward values are the one thing that distinguishes them.
    kearny = station_for("njt_bus", "15652")
    jersey_gardens = station_for("njt_bus", "15653")

    assert kearny is not None and kearny.toward == "Kearny"
    assert jersey_gardens is not None and jersey_gardens.toward == "Jersey Gardens"


def test_stations_with_no_toward_hint_carry_none():
    station = station_for("mta", "R01")

    assert station is not None
    assert station.toward is None


def test_station_for_returns_real_coordinates():
    station = station_for("path", "JSQ")

    assert station is not None
    assert station.lat == 40.7318097
    assert station.lng == -74.0628655


def test_nearest_stations_finds_a_real_close_station():
    # Real coordinates right at Journal Square PATH's own location -
    # should find itself as (one of) the nearest, at ~0 distance.
    results = nearest_stations(40.7318097, -74.0628655, limit=1, agency="path")

    assert len(results) == 1
    assert results[0].station.code == "JSQ"
    assert results[0].distance_miles < 0.1


def test_nearest_stations_sorts_by_real_distance_nearest_first():
    # Newark (NJ) is much farther from Journal Square's coordinates than
    # Journal Square itself - a real ordering check, not just "one result".
    results = nearest_stations(40.7318097, -74.0628655, limit=5, agency="path")

    assert len(results) > 1
    distances = [r.distance_miles for r in results]
    assert distances == sorted(distances)


def test_nearest_stations_respects_agency_filter():
    # Searching only "path" should never return a non-PATH station, even
    # if a closer real station of another agency exists nearby.
    results = nearest_stations(40.7318097, -74.0628655, limit=5, agency="path")

    assert all(r.station.agency == "path" for r in results)


def test_nearest_stations_searches_every_agency_when_none_specified():
    results = nearest_stations(40.7318097, -74.0628655, limit=5, agency=None)

    agencies = {r.station.agency for r in results}
    assert len(agencies) >= 1  # not asserting a specific mix - just that it's unrestricted


def test_nearest_stations_respects_limit():
    results = nearest_stations(40.7318097, -74.0628655, limit=2)

    assert len(results) <= 2
