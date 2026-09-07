from types import SimpleNamespace

import pytest

from live.demo_mt5 import DemoExecutionError, LONG, MT5DemoExecutionAdapter


class FakeMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    SYMBOL_TRADE_EXECUTION_MARKET = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    ORDER_FILLING_RETURN = 2
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    POSITION_TYPE_BUY = 0
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010

    def __init__(self, *, trade_mode=0):
        self.account = SimpleNamespace(
            login=123,
            server="Demo-Server",
            company="Demo Broker",
            trade_mode=trade_mode,
            trade_allowed=True,
            trade_expert=True,
            currency="USD",
            balance=10000.0,
            equity=10000.0,
            margin_free=10000.0,
        )
        self.symbol = SimpleNamespace(
            visible=True,
            digits=5,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            filling_mode=1,
            trade_exemode=1,
        )
        self.sent = []

    def initialize(self, path=None):
        return True

    def shutdown(self):
        return None

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        return self.account

    def terminal_info(self):
        return SimpleNamespace(trade_allowed=True)

    def positions_get(self, symbol=None, ticket=None):
        return ()

    def symbol_info(self, symbol):
        return self.symbol

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(ask=1.10125, bid=1.10115)

    def symbol_select(self, symbol, enabled):
        return enabled

    def order_check(self, request):
        return SimpleNamespace(retcode=0, comment="Done")

    def order_send(self, request):
        self.sent.append(request)
        return SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE,
            volume=request["volume"],
            price=request["price"],
            order=456,
            deal=789,
            comment="Done",
        )


def test_demo_guard_rejects_real_account():
    mt5 = FakeMT5(trade_mode=2)
    adapter = MT5DemoExecutionAdapter(mt5)

    with pytest.raises(DemoExecutionError, match="DEMO-ONLY"):
        adapter.connect()

    assert mt5.sent == []


def test_demo_open_checks_then_sends_one_order():
    mt5 = FakeMT5()
    adapter = MT5DemoExecutionAdapter(mt5, max_volume=0.10)
    adapter.connect()

    result = adapter.open_market(
        client_order_id="ARIA-EURUSD-15m-20260907T080000Z-LONG",
        symbol="EURUSD",
        direction=LONG,
        volume=0.01,
        stop_loss=1.09925,
        take_profit=1.10525,
    )

    assert result.status == "FILLED"
    assert result.broker_order_id == "456"
    assert mt5.sent[0]["volume"] == 0.01
    assert mt5.sent[0]["sl"] == 1.09925
    assert mt5.sent[0]["tp"] == 1.10525


def test_volume_above_hard_demo_cap_never_reaches_order_check():
    mt5 = FakeMT5()
    adapter = MT5DemoExecutionAdapter(mt5, max_volume=0.05)
    adapter.connect()

    with pytest.raises(DemoExecutionError, match="max_volume"):
        adapter.open_market(
            client_order_id="ARIA-TOO-LARGE",
            symbol="EURUSD",
            direction=LONG,
            volume=0.10,
            stop_loss=1.09925,
            take_profit=1.10525,
        )

    assert mt5.sent == []
