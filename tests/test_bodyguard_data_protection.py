from bodyguard.data_protection import REDACTED, sanitize_for_boundary, sanitize_log_record, sanitize_public_payload


def test_sensitive_keys_are_redacted_recursively():
    payload = {
        "symbol": "EUR/USD",
        "credentials": {"api_key": "secret-value", "password": "hunter2"},
        "nested": [{"authorization": "Bearer abcdefghijklmnop"}],
    }

    result = sanitize_for_boundary(payload)

    assert result["symbol"] == "EUR/USD"
    assert result["credentials"]["api_key"] == REDACTED
    assert result["credentials"]["password"] == REDACTED
    assert result["nested"][0]["authorization"] == REDACTED


def test_secret_shaped_values_are_redacted_even_without_sensitive_key():
    payload = {
        "message": "Authorization: Bearer abcdefghijklmnop",
        "token_dump": "eyJaaaaaaaaaaaa.bbbbbbbbbbbb.cccccccccccc",
        "key": "ghp_abcdefghijklmnopqrstuvwxyz123456",
    }

    result = sanitize_public_payload(payload)

    assert REDACTED in result["message"]
    assert REDACTED in result["token_dump"]
    assert REDACTED in result["key"]


def test_bounded_depth_and_collection_size():
    deep = {"a": {"b": {"c": {"d": {"e": {"f": "secret"}}}}}}
    wide = {str(i): i for i in range(250)}

    assert sanitize_for_boundary(deep, max_depth=3)["a"]["b"]["c"] == REDACTED
    result = sanitize_for_boundary(wide, max_items=10)
    assert len(result) == 11
    assert result["[TRUNCATED]"] == REDACTED


def test_unknown_objects_are_stringified_without_custom_serialization():
    class SensitiveObject:
        def __str__(self):
            return "Bearer abcdefghijklmnop"

    result = sanitize_for_boundary({"object": SensitiveObject()})
    assert result["object"] == f"{REDACTED}"


def test_log_record_and_public_payload_require_mappings():
    assert sanitize_log_record({"password": "secret"})["password"] == REDACTED
    assert sanitize_public_payload({"api_key": "secret"})["api_key"] == REDACTED
