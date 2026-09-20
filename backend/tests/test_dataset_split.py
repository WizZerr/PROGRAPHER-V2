from app.datasets.split import assign_event_splits


def test_split_is_event_level_and_deterministic() -> None:
    events = [f"event-{index}" for index in range(12)]

    first = assign_event_splits(events, seed="same-seed")
    second = assign_event_splits(reversed(events), seed="same-seed")

    assert first == second
    assert set(first) == set(events)
    assert "train" in set(first.values())
    assert "validation" in set(first.values())
    assert "test" in set(first.values())


def test_single_event_is_never_split_by_photo() -> None:
    result = assign_event_splits(["same-wedding"])

    assert result == {"same-wedding": "train"}
