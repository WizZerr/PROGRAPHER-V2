from pathlib import Path

from app.evaluation.legacy_inventory import inventory_legacy


def test_inventory_never_claims_reconstruction_when_artifacts_are_missing(
    tmp_path: Path,
) -> None:
    (tmp_path / "vision.py").write_text(
        "CLIP = True\n",
        encoding="utf-8",
    )
    (tmp_path / "profile_ai.py").write_text(
        "from sklearn.ensemble import ExtraTreesRegressor\n",
        encoding="utf-8",
    )

    report = inventory_legacy(tmp_path)

    assert report["clip_detected_in_source"] is True
    assert report["extratrees_detected_in_source"] is True
    assert report["required_sources_present"] is False
    assert report["model_artifact_count"] == 0
    assert report["reconstruction_state"] == "incomplete"
