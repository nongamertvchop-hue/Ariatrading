from strategy.market_structure import UNKNOWN
from strategy.ml_features import MLSample
from strategy.regime import REGIMES, classify_regime, stratify_samples


def candles(n=20):
    return [
        {"time": i, "open": 100 + i, "high": 102 + i, "low": 99 + i, "close": 101 + i}
        for i in range(n)
    ]


def test_classify_regime_uses_only_prefix():
    data = candles()
    before = classify_regime(data, 10)
    mutated = list(data)
    mutated[19] = {"time": 19, "open": 1, "high": 1000, "low": 0.5, "close": 2}
    assert classify_regime(mutated, 10) == before


def test_early_regime_is_unknown_when_structure_is_insufficient():
    assert classify_regime(candles(), 0) == UNKNOWN


def test_stratify_samples_returns_all_regimes_and_rates():
    data = candles()
    samples = [
        MLSample(index=0, timestamp=0, features=(0.0,), label=1),
        MLSample(index=1, timestamp=1, features=(0.0,), label=0),
    ]
    result = stratify_samples(data, samples)
    assert tuple(item.regime for item in result) == REGIMES
    unknown = next(item for item in result if item.regime == UNKNOWN)
    assert unknown.samples == 2
    assert unknown.positive == 1
    assert unknown.positive_rate == 0.5


def test_stratify_rejects_invalid_sample_index():
    try:
        stratify_samples(candles(), [MLSample(index=99, timestamp=0, features=(0.0,), label=1)])
    except ValueError as exc:
        assert "sample index" in str(exc)
    else:
        raise AssertionError("expected ValueError")
