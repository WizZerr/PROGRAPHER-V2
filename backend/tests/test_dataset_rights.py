from app.datasets.contracts import DatasetRights


def test_general_training_is_opt_in() -> None:
    rights = DatasetRights(
        permission_basis="photographer_owned",
        allow_personal_training=True,
    )

    assert rights.allow_personal_training is True
    assert rights.allow_general_training is False
