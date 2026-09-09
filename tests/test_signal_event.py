from strategy.signal_event import build_signal_event_id, canonical_signal_event


def test_signal_event_id_matches_worker_contract_vector():
    payload = {
        "symbol": "EUR/USD",
        "timeframe": "15m",
        "bar_time": "2026-09-08T19:15:00Z",
        "signal": "WAIT",
        "state": "APPROACH",
        "breakout_state": "NO_BREAKOUT",
        "price": 1.1025,
        "entry_reference": None,
        "stop_reference": None,
        "structure_bias": "RANGE",
        "score": None,
        "zone": None,
        "generated_at": "2026-09-08T19:16:00Z",
    }

    assert canonical_signal_event(payload) == (
        '["EUR/USD","15m","2026-09-08T19:15:00Z","WAIT","APPROACH",'
        '"NO_BREAKOUT",1.1025,null,null,"RANGE",null,null]'
    )
    assert build_signal_event_id(payload) == "sig_9bf358bd9e1b18cc12aff86774938787"


def test_generated_at_does_not_change_event_identity():
    payload = {
        "symbol": "EUR/USD",
        "timeframe": "15m",
        "bar_time": "2026-09-08T19:15:00Z",
        "signal": "WAIT",
        "state": "APPROACH",
        "breakout_state": "NO_BREAKOUT",
        "price": 1.1025,
        "entry_reference": None,
        "stop_reference": None,
        "structure_bias": "RANGE",
        "score": None,
        "zone": None,
    }

    first = build_signal_event_id(payload)
    second = build_signal_event_id({**payload, "generated_at": "2026-09-08T19:17:00Z"})
    assert first == second


def test_closed_candle_decision_changes_event_identity():
    payload = {
        "symbol": "EUR/USD",
        "timeframe": "15m",
        "bar_time": "2026-09-08T19:15:00Z",
        "signal": "WAIT",
        "state": "APPROACH",
        "breakout_state": "NO_BREAKOUT",
        "price": 1.1025,
        "entry_reference": None,
        "stop_reference": None,
        "structure_bias": "RANGE",
        "score": None,
        "zone": None,
    }

    first = build_signal_event_id(payload)
    changed = build_signal_event_id({**payload, "signal": "LONG"})
    assert first != changed
