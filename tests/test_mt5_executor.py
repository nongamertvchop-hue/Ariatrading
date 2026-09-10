from datetime import datetime, timezone

import pytest

from live.mt5_executor import MT5LiveExecutor, ORDER_BUY, ORDER_SELL


class FakeMT5Module:
    """Mock MT5 module for testing executor logic."""

    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_OUT_BY = 3

    def __init__(self) -> None:
        self.last_req = None
        self.should_fail = False

    def initialize(self, **kwargs):
        return True

    def shutdown(self):
        return True

    def last_error(self):
        return (0, "ok")

    def account_info(self):
        class Account:
            login = 123456
            balance = 10000.0
            equity = 9950.0
            margin_free = 9000.0
            trade_allowed = True
            trade_expert = True

        return Account()

    def symbol_info(self, symbol):
        class SymbolInfo:
            name = symbol
            digits = 5
            point = 0.00001
            trade_tick_value = 1.0
            trade_tick_size = 0.00001
            volume_min = 0.01
            volume_max = 100.0
            volume_step = 0.01
            visible = True
            filling_mode = 1

        return SymbolInfo()

    def symbol_select(self, symbol, enable):
        return True

    def symbol_info_tick(self, symbol):
        class Tick:
            time = int(datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc).timestamp())
            bid = 1.10000
            ask = 1.10015
            last = 1.10005
            volume = 100

        return Tick()

    def order_send(self, req):
        self.last_req = req
        if self.should_fail:
            class FailedRes:
                retcode = 10013
                comment = "Invalid volume"

            return FailedRes()

        class DoneRes:
            retcode = 10009
            order = 123456
            deal = 789012
            price = req["price"]
            volume = req["volume"]
            comment = "Request executed"

        return DoneRes()

    def positions_get(self, **kwargs):
        class Pos:
            ticket = 123456
            symbol = "EURUSD"
            type = 0
            volume = 0.50
            price_open = 1.10015
            sl = 1.09800
            tp = 1.10300
            profit = 25.0
            magic = 8808
            time = int(datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc).timestamp())

        return [Pos()]


def test_mt5_executor_connect_and_contract():
    mock_mt5 = FakeMT5Module()
    executor = MT5LiveExecutor(mt5_module=mock_mt5, magic_number=8808)
    assert executor.connect()

    contract = executor.get_symbol_contract("EURUSD")
    assert contract.symbol == "EURUSD"
    assert contract.digits == 5
    assert contract.point == 0.00001
    assert contract.volume_min == 0.01


def test_mt5_executor_reads_account_snapshot():
    executor = MT5LiveExecutor(mt5_module=FakeMT5Module())
    executor.connect()

    account = executor.get_account_snapshot()

    assert account.login == 123456
    assert account.balance == 10000.0
    assert account.equity == 9950.0
    assert account.margin_free == 9000.0
    assert account.trade_allowed is True
    assert account.trade_expert is True


def test_mt5_executor_buy_order_success():
    mock_mt5 = FakeMT5Module()
    executor = MT5LiveExecutor(mt5_module=mock_mt5, magic_number=8808)
    executor.connect()

    res = executor.send_market_order(
        symbol="EURUSD",
        direction=ORDER_BUY,
        volume=0.5,
        sl=1.09800,
        tp=1.10400,
        deviation_points=10,
    )
    assert res.success
    assert res.ticket == 123456
    assert mock_mt5.last_req["type"] == mock_mt5.ORDER_TYPE_BUY
    assert mock_mt5.last_req["sl"] == 1.09800
    assert mock_mt5.last_req["tp"] == 1.10400
    assert mock_mt5.last_req["magic"] == 8808


def test_mt5_executor_rejects_invalid_volume_and_tp():
    executor = MT5LiveExecutor(mt5_module=FakeMT5Module())
    executor.connect()

    assert not executor.send_market_order(
        symbol="EURUSD", direction=ORDER_BUY, volume=0, sl=1.09800
    ).success
    assert not executor.send_market_order(
        symbol="EURUSD", direction=ORDER_BUY, volume=0.1, sl=1.09800, tp=0
    ).success


def test_mt5_executor_sell_order_validation():
    mock_mt5 = FakeMT5Module()
    executor = MT5LiveExecutor(mt5_module=mock_mt5, magic_number=8808)
    executor.connect()

    res = executor.send_market_order(
        symbol="EURUSD",
        direction=ORDER_SELL,
        volume=0.5,
        sl=1.09000,
    )
    assert not res.success
    assert "SELL Stop Loss must be above entry price" in res.error_message


def test_mt5_executor_positions_and_close():
    mock_mt5 = FakeMT5Module()
    executor = MT5LiveExecutor(mt5_module=mock_mt5, magic_number=8808)
    executor.connect()

    positions = executor.get_open_positions()
    assert len(positions) == 1
    assert positions[0].ticket == 123456
    assert positions[0].symbol == "EURUSD"

    close_res = executor.close_position(123456)
    assert close_res.success
    assert close_res.ticket == 123456


def test_mt5_executor_cannot_close_foreign_strategy_position():
    mock_mt5 = FakeMT5Module()

    class ForeignPositionModule(FakeMT5Module):
        def positions_get(self, **kwargs):
            rows = super().positions_get(**kwargs)
            rows[0].magic = 9999
            return rows

    executor = MT5LiveExecutor(mt5_module=ForeignPositionModule(), magic_number=8808)
    executor.connect()

    result = executor.close_position(123456)
    assert not result.success
    assert "not owned by this strategy" in result.error_message
