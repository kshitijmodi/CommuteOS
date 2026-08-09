from app.path_topology import PathLeg, route_between_stations


def test_same_station_returns_empty_list():
    assert route_between_stations("NWK", "NWK") == []


def test_direct_ride_on_hob_33_needs_no_transfer():
    # Real fact confirmed via research: Hoboken<->33rd St is a genuine
    # one-seat ride on the HOB_33 route, unlike Newark<->Hoboken/33rd St.
    legs = route_between_stations("HOB", "33S")

    assert legs == [PathLeg(route="HOB_33", board_code="HOB", alight_code="33S")]


def test_direct_ride_works_in_reverse_direction_too():
    legs = route_between_stations("33S", "HOB")

    assert legs == [PathLeg(route="HOB_33", board_code="33S", alight_code="HOB")]


def test_newark_to_hoboken_requires_a_real_transfer():
    # Real fact confirmed via research: no one-seat Newark<->Hoboken ride
    # exists on PATH's standard service - riders transfer, and Exchange
    # Place (on both NWK_WTC and HOB_WTC) is a genuine real transfer point.
    legs = route_between_stations("NWK", "HOB")

    assert len(legs) == 2
    assert legs[0].route == "NWK_WTC"
    assert legs[0].board_code == "NWK"
    assert legs[1].route == "HOB_WTC"
    assert legs[1].alight_code == "HOB"
    # The transfer station must be the same real place both legs agree on.
    assert legs[0].alight_code == legs[1].board_code


def test_newark_to_33rd_st_requires_a_transfer_at_journal_square_or_grove():
    # Real fact confirmed via research: "transfer to the Journal
    # Square-33rd Street service at Journal Square or Grove Street."
    legs = route_between_stations("NWK", "33S")

    assert len(legs) == 2
    assert legs[0].alight_code in {"JSQ", "GRV"}
    assert legs[1].board_code == legs[0].alight_code
    assert legs[1].alight_code == "33S"


def test_journal_square_and_grove_street_are_a_direct_ride():
    # Both stations sit on the same NWK_WTC route (and also JSQ_33) - a
    # real one-seat ride, not requiring the transfer logic at all.
    legs = route_between_stations("JSQ", "GRV")

    assert len(legs) == 1
    assert legs[0].board_code == "JSQ"
    assert legs[0].alight_code == "GRV"


class TestPathLegDirection:
    def test_toward_ny_when_alighting_further_along_the_route(self):
        leg = PathLeg(route="NWK_WTC", board_code="NWK", alight_code="WTC")

        assert leg.direction == "ToNY"

    def test_toward_nj_when_alighting_earlier_in_the_route(self):
        leg = PathLeg(route="NWK_WTC", board_code="WTC", alight_code="NWK")

        assert leg.direction == "ToNJ"

    def test_direction_is_correct_on_every_real_leg_of_a_transfer_trip(self):
        legs = route_between_stations("NWK", "HOB")

        assert legs[0].direction == "ToNY"  # Newark -> Exchange Place, heading toward NY
        assert legs[1].direction == "ToNJ"  # Exchange Place -> Hoboken, heading toward NJ
