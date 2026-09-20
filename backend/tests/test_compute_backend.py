from app.services.compute_backend import detect_compute_backend


def test_compute_detection_always_has_cpu_fallback() -> None:
    report = detect_compute_backend()

    assert report.cpu_available is True
    assert report.selected_backend in {"cpu", "cuda", "mps"}
    assert report.os
    assert report.architecture


def test_compute_detection_does_not_claim_model_quality() -> None:
    report = detect_compute_backend()

    assert "accuracy" in report.note.lower() or "quality" in report.note.lower()
