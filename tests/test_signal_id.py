"""Tests for deterministic signal ID generation and registry."""

from datetime import datetime, timezone

import pytest

from strategy.levels_v2 import PriceZone, SUPPORT, RESISTANCE
from strategy.signal_id import SignalRegistry, make_signal_id


def test_make_signal_id_stable():
    zone = PriceZone(kind=SUPPORT, low=1.0800, high=1.0810, touches=3)
    id1 = make_signal_id(
        symbol="EURUSD",
        timeframe="15m",
        action="LONG",
        confirmation_index=42,
        zone=zone,
    )
    id2 = make_signal_id(
        symbol="EURUSD",
        timeframe="15m",
        action="LONG",
        confirmation_index=42,
        zone=zone,
    )
    assert id1 == id2
    assert id1.startswith("sig_")
    assert len(id1) == 16  # sig_ + 12 hex


def test_make_signal_id_different_inputs_differ():
    zone = PriceZone(kind=SUPPORT, low=1.0800, high=1.0810, touches=3)
    base = dict(symbol="EURUSD", timeframe="15m", action="LONG", confirmation_index=42, zone=zone)
    id_a = make_signal_id(**base)
    id_b = make_signal_id(**{**base, "confirmation_index": 43})
    id_c = make_signal_id(**{**base, "action": "SHORT"})
    assert id_a != id_b
    assert id_a != id_c


def test_registry_deduplication():
    reg = SignalRegistry()
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)

    is_new1, rec1 = reg.register(
        "sig_abc123def456",
        symbol="EURUSD",
        timeframe="15m",
        action="LONG",
        now=now,
    )
    assert is_new1 is True
    assert rec1.count == 1

    is_new2, rec2 = reg.register(
        "sig_abc123def456",
        symbol="EURUSD",
        timeframe="15m",
        action="LONG",
        now=now,
    )
    assert is_new2 is False
    assert rec2.count == 2
    assert rec2.first_seen == now

    assert len(reg) == 1
    assert reg.has("sig_abc123def456")
    assert not reg.has("sig_nonexistent")
