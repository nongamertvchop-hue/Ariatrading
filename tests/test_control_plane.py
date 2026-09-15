from live.control_plane import BotControlPlane, EMERGENCY_STOP, PAUSE, RUN, STOP


def test_control_plane_defaults_to_stop(tmp_path):
    control = BotControlPlane(tmp_path / "bot.json")
    state = control.read()
    assert state.state == STOP
    assert state.generation == 0
    assert control.can_trade() is False


def test_control_plane_transitions_are_persistent(tmp_path):
    path = tmp_path / "bot.json"
    control = BotControlPlane(path)

    started = control.set(RUN, "start demo")
    assert started.state == RUN
    assert started.generation == 1
    assert control.can_trade() is True

    restarted = BotControlPlane(path)
    assert restarted.read().state == RUN
    assert restarted.read().generation == 1

    paused = restarted.set(PAUSE, "pause for review")
    assert paused.generation == 2
    assert restarted.can_trade() is False


def test_emergency_stop_is_not_tradeable(tmp_path):
    control = BotControlPlane(tmp_path / "bot.json")
    state = control.set(EMERGENCY_STOP, "risk event")
    assert state.state == EMERGENCY_STOP
    assert control.can_trade() is False


def test_invalid_state_rejected(tmp_path):
    control = BotControlPlane(tmp_path / "bot.json")
    try:
        control.set("RUNNING")
    except ValueError as exc:
        assert "unsupported bot state" in str(exc)
    else:
        raise AssertionError("invalid state was accepted")
