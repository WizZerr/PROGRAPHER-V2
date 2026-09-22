from __future__ import annotations

from app.brain_v2.training.dataset_manifest import (
    DatasetImportManifest,
    DatasetManifestSample,
)
from app.brain_v2.training.event_split import (
    build_event_safe_split,
)


def _sample(
    *,
    sample_id: str,
    event_id: str,
    ready: bool = True,
) -> DatasetManifestSample:
    return DatasetManifestSample(
        sample_id=sample_id,
        event_id=event_id,
        raw_path=f"C:/data/{event_id}/{sample_id}.cr3",
        raw_relpath=f"{event_id}/{sample_id}.cr3",
        raw_sha256=(sample_id * 64)[:64],
        xmp_path=(
            f"C:/data/{event_id}/{sample_id}.cr3.xmp"
            if ready else None
        ),
        xmp_relpath=(
            f"{event_id}/{sample_id}.cr3.xmp"
            if ready else None
        ),
        xmp_sha256=((sample_id + "x") * 64)[:64] if ready else None,
        pair_status="paired" if ready else "missing_xmp",
        target_status="ready" if ready else "missing_xmp",
        ready_for_three_target_training=ready,
        targets=(
            {
                "exposure_stops": 0.1,
                "temperature_k": 5200,
                "tint": 2,
            }
            if ready else None
        ),
        missing_target_fields=(),
        rendering_context=(
            {
                "process_version": "11.0",
                "camera_profile": "Adobe Standard",
                "tone_curve": "Medium Contrast",
                "preset_identity": "none",
            }
            if ready else None
        ),
        error=None,
    )


def _manifest(samples, dataset_id="d" * 64):
    usable = tuple(
        sorted(
            {
                sample.event_id
                for sample in samples
                if sample.ready_for_three_target_training
            }
        )
    )
    return DatasetImportManifest(
        dataset_id=dataset_id,
        dataset_root="C:/data",
        sample_count=len(samples),
        training_ready_count=sum(
            1 for sample in samples
            if sample.ready_for_three_target_training
        ),
        event_count=len({sample.event_id for sample in samples}),
        usable_event_ids=usable,
        event_safe_split_ready=len(usable) >= 2,
        source_readiness_schema_version="phase12-dataset-readiness-v1",
        samples=tuple(samples),
    )


def test_two_events_are_never_split_across_both_sides() -> None:
    manifest = _manifest(
        [
            _sample(sample_id="a1", event_id="event-a"),
            _sample(sample_id="a2", event_id="event-a"),
            _sample(sample_id="b1", event_id="event-b"),
            _sample(sample_id="b2", event_id="event-b"),
        ]
    )

    split = build_event_safe_split(manifest)

    assert len(split.train_event_ids) == 1
    assert len(split.validation_event_ids) == 1
    assert set(split.train_event_ids).isdisjoint(
        split.validation_event_ids
    )

    by_event = {}
    for assignment in split.sample_assignments:
        by_event.setdefault(assignment.event_id, set()).add(
            assignment.split
        )
    assert all(len(values) == 1 for values in by_event.values())


def test_split_is_deterministic_for_same_dataset_and_seed() -> None:
    samples = [
        _sample(sample_id="a1", event_id="event-a"),
        _sample(sample_id="b1", event_id="event-b"),
        _sample(sample_id="c1", event_id="event-c"),
    ]
    manifest = _manifest(samples)

    first = build_event_safe_split(
        manifest,
        validation_fraction=0.34,
        seed="fixed",
    )
    second = build_event_safe_split(
        manifest,
        validation_fraction=0.34,
        seed="fixed",
    )

    assert first.split_id == second.split_id
    assert first.event_assignments == second.event_assignments
    assert first.sample_assignments == second.sample_assignments


def test_input_sample_order_does_not_change_split() -> None:
    samples = [
        _sample(sample_id="a1", event_id="event-a"),
        _sample(sample_id="b1", event_id="event-b"),
        _sample(sample_id="c1", event_id="event-c"),
    ]

    first = build_event_safe_split(_manifest(samples), seed="fixed")
    second = build_event_safe_split(
        _manifest(list(reversed(samples))),
        seed="fixed",
    )

    assert first.train_event_ids == second.train_event_ids
    assert first.validation_event_ids == second.validation_event_ids
    assert first.sample_assignments == second.sample_assignments


def test_non_ready_samples_receive_no_split_assignment() -> None:
    manifest = _manifest(
        [
            _sample(sample_id="a1", event_id="event-a"),
            _sample(sample_id="b1", event_id="event-b"),
            _sample(
                sample_id="bad",
                event_id="event-a",
                ready=False,
            ),
        ]
    )

    split = build_event_safe_split(manifest)

    assert {item.sample_id for item in split.sample_assignments} == {
        "a1",
        "b1",
    }


def test_split_id_is_bound_to_dataset_identity() -> None:
    samples = [
        _sample(sample_id="a1", event_id="event-a"),
        _sample(sample_id="b1", event_id="event-b"),
    ]

    first = build_event_safe_split(
        _manifest(samples, dataset_id="a" * 64)
    )
    second = build_event_safe_split(
        _manifest(samples, dataset_id="b" * 64)
    )

    assert first.split_id != second.split_id


def test_rejects_fewer_than_two_usable_events() -> None:
    manifest = _manifest(
        [_sample(sample_id="a1", event_id="event-a")]
    )

    try:
        build_event_safe_split(manifest)
    except ValueError as exc:
        assert "At least two usable events" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
