from datetime import datetime, timezone

import pytest

from strategy.deep_learning import build_causal_sequences
from strategy.ml_features import MLSample


def _sample(index, label=None):
    return MLSample(
        index=index,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        features=(float(index), float(index % 3)),
        label=index % 2 if label is None else label,
    )


def test_causal_sequences_use_only_history_and_current_target():
    history = [_sample(i) for i in range(4)]
    target = [_sample(i, label=i % 2) for i in range(4, 7)]

    sequences, labels = build_causal_sequences(history, target, sequence_length=3)

    assert len(sequences) == 3
    assert sequences[0][0][0] == 2.0
    assert sequences[0][-1][0] == 4.0
    assert sequences[-1][-1][0] == 6.0
    assert labels == (0, 1, 0)


def test_sequence_builder_rejects_non_chronological_history():
    with pytest.raises(ValueError, match="strictly precede"):
        build_causal_sequences([_sample(2)], [_sample(2)], sequence_length=2)


def test_sequence_builder_requires_enough_context():
    with pytest.raises(ValueError, match="not enough"):
        build_causal_sequences([_sample(0)], [_sample(1)], sequence_length=3)


def test_deep_learning_training_is_optional():
    pytest.importorskip("torch")
