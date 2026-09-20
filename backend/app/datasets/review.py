from __future__ import annotations

from dataclasses import replace
from typing import Literal

from app.datasets.contracts import DatasetCandidate, DatasetPreview


ReviewDecision = Literal["verified_final", "rejected"]


def review_candidate(
    candidate: DatasetCandidate,
    *,
    decision: ReviewDecision,
) -> DatasetCandidate:
    if decision == "rejected":
        reasons = tuple(
            dict.fromkeys(
                [*candidate.exclusion_reasons, "human_rejected"]
            )
        )
        return replace(
            candidate,
            final_edit_state="rejected",
            final_edit_verified=False,
            exclusion_reasons=reasons,
            usable_for_training=False,
        )

    if candidate.pair_status != "matched":
        raise ValueError(
            "אי אפשר לאמת עריכה סופית ללא זוג RAW ↔ עריכה חד-משמעי."
        )

    usable = len(candidate.exclusion_reasons) == 0

    return replace(
        candidate,
        final_edit_state="verified_final",
        final_edit_verified=True,
        usable_for_training=usable,
    )


def apply_review_decisions(
    preview: DatasetPreview,
    decisions_by_fingerprint: dict[str, ReviewDecision],
) -> DatasetPreview:
    reviewed: list[DatasetCandidate] = []

    for candidate in preview.candidates:
        decision = decisions_by_fingerprint.get(candidate.source.fingerprint)

        if decision is None:
            reviewed.append(candidate)
            continue

        reviewed.append(
            review_candidate(
                candidate,
                decision=decision,
            )
        )

    verified_training_pairs = sum(
        candidate.usable_for_training for candidate in reviewed
    )

    return replace(
        preview,
        verified_training_pairs=verified_training_pairs,
        candidates=tuple(reviewed),
    )
