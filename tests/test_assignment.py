import pytest

from macronet.domain.assignment import AssignmentError, Link, assign_all_or_nothing


def test_all_or_nothing_uses_the_minimum_cost_path() -> None:
    links = (
        Link("AB", "A", "B", 2.0, 80.0),
        Link("BC", "B", "C", 2.0, 80.0),
        Link("AC", "A", "C", 10.0, 200.0),
        Link("BA", "B", "A", 2.0, 80.0),
        Link("CB", "C", "B", 2.0, 80.0),
        Link("CA", "C", "A", 10.0, 200.0),
    )
    demand = ((10.0, 0.0, 100.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    result = assign_all_or_nothing(("A", "B", "C"), ("A", "B", "C"), demand, links)

    interzonal_path = next(path for path in result.paths if path.destination == "C")
    assert interzonal_path.nodes == ("A", "B", "C")
    assert interzonal_path.link_ids == ("AB", "BC")
    assert interzonal_path.cost == 4.0
    volumes = {item.link.link_id: item.volume for item in result.link_results}
    assert volumes["AB"] == 100.0
    assert volumes["BC"] == 100.0
    assert volumes["AC"] == 0.0


def test_intrazonal_demand_does_not_load_links() -> None:
    links = (Link("AB", "A", "B", 1.0, 100.0), Link("BA", "B", "A", 1.0, 100.0))
    result = assign_all_or_nothing(
        ("A", "B"),
        ("A", "B"),
        ((25.0, 0.0), (0.0, 0.0)),
        links,
    )

    assert result.intrazonal_demand == 25.0
    assert result.assigned_demand == 0.0
    assert all(item.volume == 0.0 for item in result.link_results)


def test_volume_capacity_ratio_is_reported() -> None:
    links = (Link("AB", "A", "B", 1.0, 40.0), Link("BA", "B", "A", 1.0, 40.0))
    result = assign_all_or_nothing(
        ("A", "B"),
        ("A", "B"),
        ((0.0, 50.0), (0.0, 0.0)),
        links,
    )

    ab_result = next(item for item in result.link_results if item.link.link_id == "AB")
    assert ab_result.volume_capacity_ratio == pytest.approx(1.25)


def test_disconnected_od_pair_is_rejected() -> None:
    links = (Link("AB", "A", "B", 1.0, 100.0),)

    with pytest.raises(AssignmentError, match="No existe una ruta"):
        assign_all_or_nothing(
            ("A", "B"),
            ("A", "B"),
            ((0.0, 0.0), (10.0, 0.0)),
            links,
        )
