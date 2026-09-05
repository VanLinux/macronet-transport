from macronet.domain.four_step import FOUR_STEP_SEQUENCE, FourStepStage


def test_four_step_sequence_has_the_canonical_order() -> None:
    assert FOUR_STEP_SEQUENCE == (
        FourStepStage.TRIP_GENERATION,
        FourStepStage.TRIP_DISTRIBUTION,
        FourStepStage.MODE_CHOICE,
        FourStepStage.TRAFFIC_ASSIGNMENT,
    )


def test_stage_slugs_are_unique() -> None:
    slugs = [stage.slug for stage in FOUR_STEP_SEQUENCE]
    assert len(slugs) == len(set(slugs))
