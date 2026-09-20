from app.core.execution_policy import responsibility_map


def test_raw_and_event_state_are_local() -> None:
    policy = responsibility_map()

    assert policy["raw_access"] == "local"
    assert policy["event_index"] == "local"
    assert policy["cache"] == "local"
    assert policy["photographer_decisions"] == "local"
    assert policy["export"] == "local"


def test_account_and_remote_training_are_not_required_for_local_pilot() -> None:
    policy = responsibility_map()

    assert policy["account"] == "remote_optional"
    assert policy["license"] == "remote_optional"
    assert policy["model_download"] == "remote_optional"
    assert policy["remote_training"] == "remote_optional"

    assert policy["registration"] == "out_of_scope_for_local_pilot"
    assert policy["payment"] == "out_of_scope_for_local_pilot"
