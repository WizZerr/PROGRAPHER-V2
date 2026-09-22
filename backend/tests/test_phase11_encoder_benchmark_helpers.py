import numpy as np

from app.brain_v2.vision_encoders.benchmark import (
    classify_model_load_error,
    vector_sha256,
)


def test_vector_hash_is_stable_for_float32_representation() -> None:
    first = vector_sha256((1.0, 2.0, 3.0))
    second = vector_sha256(
        tuple(float(x) for x in np.array([1, 2, 3], dtype=np.float32))
    )

    assert first == second


def test_gated_error_is_classified_as_blocked_access() -> None:
    error = RuntimeError(
        "GatedRepoError: Access to model is restricted"
    )

    assert classify_model_load_error(error) == "gated_or_unauthorized"


def test_network_error_is_classified_separately() -> None:
    error = RuntimeError("Connection timeout while downloading")

    assert classify_model_load_error(error) == "network_error"
