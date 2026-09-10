from live.notifier import NotificationConfig, Notifier


def test_notifier_disabled_when_empty_config():
    cfg = NotificationConfig(telegram_bot_token="", telegram_chat_id="", webhook_url="")
    notifier = Notifier(cfg)
    assert not notifier.is_configured
    # Should safely return False without network errors
    assert not notifier.send_text("Hello")


def test_notifier_formatting_calls():
    # Mocking notifier without real tokens
    cfg = NotificationConfig(telegram_bot_token="", telegram_chat_id="", webhook_url="", enabled=False)
    notifier = Notifier(cfg)

    # Calling signal formatting shouldn't raise exception
    res = notifier.notify_signal(
        symbol="EURUSD",
        direction="BUY",
        entry=1.10000,
        sl=1.09800,
        tp=1.10300,
        risk_amount=50.0,
        lot_size=0.25,
        score=8.5,
        session="LONDON+NEW_YORK",
    )
    assert not res  # Not configured

    res = notifier.notify_rejection(
        symbol="EURUSD",
        direction="BUY",
        reason="spread exceeds maximum",
    )
    assert not res
