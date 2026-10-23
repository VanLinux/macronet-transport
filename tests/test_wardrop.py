"""Casos analíticos y conservación para AON / Frank–Wolfe."""

import math

import pytest

from macronet.domain.assignment import (
    AssignmentError,
    BPRCost,
    Link,
    assign_all_or_nothing,
    assign_user_equilibrium,
    evaluate_bpr,
)
from macronet.exporters import build_assignment_csv

NAMES = ("A", "B")
OD = ((0, 1000), (0, 0))


def test_linear_two_routes_matches_document_example():
    links = (Link("r1", "A", "B", 10, 1000), Link("r2", "A", "B", 15, 1000))

    def linear(link, flow):
        return link.free_flow_time + (0.02 if link.link_id == "r1" else 0.01) * flow

    aon = assign_all_or_nothing(NAMES, NAMES, OD, links)
    ue = assign_user_equilibrium(NAMES, NAMES, OD, links, tolerance=1e-10, cost_function=linear)
    assert [r.volume for r in aon.link_results] == [1000, 0]
    assert [r.volume for r in ue.link_results] == pytest.approx([500, 500], abs=1e-7)
    assert [r.travel_time for r in ue.link_results] == pytest.approx([20, 20])
    assert ue.total_travel_time == pytest.approx(20000)
    assert ue.converged and ue.relative_gap <= 1e-10
    assert aon.converged is None


def test_bpr_parallel_links_and_fixed_aon_evaluation():
    links = (Link("a", "A", "B", 10, 1000), Link("b", "A", "B", 10, 500))
    ue = assign_user_equilibrium(NAMES, NAMES, OD, links, tolerance=1e-10)
    assert [r.volume for r in ue.link_results] == pytest.approx([2000 / 3, 1000 / 3])
    assert ue.link_results[0].travel_time == pytest.approx(ue.link_results[1].travel_time)
    aon = assign_all_or_nothing(NAMES, NAMES, OD, links)
    evaluated = evaluate_bpr(aon, 0.15, 4)
    assert evaluated.link_results[0].volume == 1000
    assert evaluated.link_results[0].travel_time == pytest.approx(11.5)
    assert aon.link_results[0].travel_time == 10
    csv = build_assignment_csv(ue, (evaluated, ue))
    assert "bpr_evaluation" in csv and "True" in csv and "Flujo_por_periodo" in csv


def test_bpr_equilibrium_conserves_flow_at_intermediate_node():
    links = (
        Link("ac", "A", "C", 5, 500),
        Link("cb", "C", "B", 5, 500),
        Link("ab", "A", "B", 12, 500),
    )
    result = assign_user_equilibrium(NAMES, NAMES, OD, links, tolerance=1e-8)
    volumes = {r.link.link_id: r.volume for r in result.link_results}
    assert volumes["ac"] == pytest.approx(volumes["cb"])
    assert volumes["ac"] + volumes["ab"] == pytest.approx(1000)
    assert all(r.volume >= 0 for r in result.link_results)


def test_final_gap_is_computed_on_final_nonconverged_flows():
    links = (
        Link("a", "A", "B", 10, 400),
        Link("b", "A", "B", 11, 400),
        Link("c", "A", "B", 12, 400),
    )
    result = assign_user_equilibrium(NAMES, NAMES, OD, links, max_iterations=1, tolerance=1e-12)
    assert not result.converged
    assert len(result.history) == 2
    t = tuple(r.travel_time for r in result.link_results)
    auxiliary = assign_all_or_nothing(NAMES, NAMES, OD, links, link_costs=t)
    shortest = sum(r.volume * r.travel_time for r in auxiliary.link_results)
    assert result.relative_gap == pytest.approx(
        (result.total_travel_time - shortest) / result.total_travel_time
    )


@pytest.mark.parametrize("od", [((0, 0), (0, 0)), ((1000, 0), (0, 0))])
def test_zero_and_intrazonal_only_demand(od):
    links = (Link("ab", "A", "B", 1, 1000),)
    result = assign_user_equilibrium(NAMES, NAMES, od, links)
    assert result.converged and result.relative_gap == 0
    assert all(r.volume == 0 for r in result.link_results)


def test_overflow_and_invalid_bpr_are_reported():
    with pytest.raises(AssignmentError):
        BPRCost(-1, 4)
    with pytest.raises(AssignmentError):
        BPRCost(0.15, math.nan)
    with pytest.raises(AssignmentError):
        BPRCost()(Link("x", "A", "B", 10, 1e-300), 1e100)


def test_tie_policy_is_reproducible_under_link_order_permutation():
    links = (Link("b", "A", "B", 10, 1000), Link("a", "A", "B", 10, 1000))
    for network in (links, tuple(reversed(links))):
        result = assign_all_or_nothing(NAMES, NAMES, OD, network)
        assert next(r for r in result.link_results if r.link.link_id == "a").volume == 1000
