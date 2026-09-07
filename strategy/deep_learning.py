"""Optional deep-learning meta-filter research for Ariatrading.

The deterministic two-setup engine remains the only source of LONG/SHORT
signals. LSTM and Transformer models only learn whether an existing signal's
follow-through label is favorable. Training and evaluation are chronological,
sequence construction is causal, and feature normalization is fitted on the
training split only.

PyTorch is intentionally an optional dependency so the core strategy and test
suite remain lightweight. Install ``requirements-ml.txt`` to use this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

from .ml_features import MLSample

ModelType = Literal["lstm", "transformer"]


@dataclass(frozen=True)
class DeepLearningMetrics:
    model_type: str
    train_samples: int
    test_samples: int
    sequence_length: int
    feature_count: int
    accuracy: float
    positive_precision: float
    positive_recall: float
    final_train_loss: float

    @property
    def valid(self) -> bool:
        return all(
            isfinite(float(value))
            for value in (
                self.accuracy,
                self.positive_precision,
                self.positive_recall,
                self.final_train_loss,
            )
        )


def _torch():
    try:
        import torch
        from torch import nn
    except ImportError as exc:
        raise RuntimeError(
            "PyTorch is required for LSTM/Transformer research; install requirements-ml.txt"
        ) from exc
    return torch, nn


def _validate_samples(samples: tuple[MLSample, ...] | list[MLSample], name: str) -> tuple[MLSample, ...]:
    result = tuple(samples)
    if not result:
        raise ValueError(f"{name} must not be empty")
    width = len(result[0].features)
    if width == 0:
        raise ValueError("features must not be empty")
    previous_index = None
    for sample in result:
        if len(sample.features) != width:
            raise ValueError("all samples must have the same feature width")
        if sample.label not in (0, 1):
            raise ValueError("labels must be 0 or 1")
        if previous_index is not None and sample.index <= previous_index:
            raise ValueError("samples must be strictly chronological")
        previous_index = sample.index
        if any(not isfinite(float(value)) for value in sample.features):
            raise ValueError("features must be finite")
    return result


def build_causal_sequences(
    history_samples: tuple[MLSample, ...] | list[MLSample],
    target_samples: tuple[MLSample, ...] | list[MLSample],
    *,
    sequence_length: int = 8,
) -> tuple[tuple[tuple[float, ...], ...], tuple[int, ...]]:
    """Build sequences ending at each target sample using past/current features."""
    if sequence_length < 2:
        raise ValueError("sequence_length must be >= 2")
    history = tuple(history_samples)
    target = _validate_samples(target_samples, "target_samples")
    if history:
        history = _validate_samples(history, "history_samples")
        if history[-1].index >= target[0].index:
            raise ValueError("history samples must strictly precede target samples")
        width = len(history[0].features)
    else:
        width = len(target[0].features)
    if len(target[0].features) != width:
        raise ValueError("history and target feature widths must match")

    combined = history + target
    target_start = len(history)
    sequences: list[tuple[tuple[float, ...], ...]] = []
    labels: list[int] = []
    for position in range(target_start, len(combined)):
        start = max(0, position - sequence_length + 1)
        window = combined[start : position + 1]
        if len(window) < sequence_length:
            continue
        sequences.append(tuple(sample.features for sample in window))
        labels.append(combined[position].label)
    return tuple(sequences), tuple(labels)


def _standardize(train_sequences, other_sequences):
    torch, _ = _torch()
    train_tensor = torch.tensor(train_sequences, dtype=torch.float32)
    other_tensor = torch.tensor(other_sequences, dtype=torch.float32)
    mean = train_tensor.mean(dim=(0, 1), keepdim=True)
    std = train_tensor.std(dim=(0, 1), keepdim=True, unbiased=False).clamp_min(1e-8)
    return (train_tensor - mean) / std, (other_tensor - mean) / std, mean, std


def _make_model(model_type: ModelType, feature_count: int, sequence_length: int, hidden_size: int, layers: int, heads: int):
    torch, nn = _torch()

    if model_type == "lstm":
        class LSTMClassifier(nn.Module):
            def __init__(self):
                super().__init__()
                self.encoder = nn.LSTM(
                    input_size=feature_count,
                    hidden_size=hidden_size,
                    num_layers=layers,
                    batch_first=True,
                    dropout=0.0 if layers == 1 else 0.1,
                )
                self.head = nn.Linear(hidden_size, 1)

            def forward(self, x):
                output, _ = self.encoder(x)
                return self.head(output[:, -1, :]).squeeze(-1)

        return LSTMClassifier()

    if model_type == "transformer":
        if hidden_size % heads != 0:
            raise ValueError("hidden_size must be divisible by heads for Transformer")

        class PositionalEncoding(nn.Module):
            def __init__(self):
                super().__init__()
                position = torch.arange(sequence_length, dtype=torch.float32).unsqueeze(1)
                div = torch.exp(torch.arange(0, hidden_size, 2, dtype=torch.float32) * (-__import__("math").log(10000.0) / hidden_size))
                encoding = torch.zeros(sequence_length, hidden_size)
                encoding[:, 0::2] = torch.sin(position * div)
                encoding[:, 1::2] = torch.cos(position * div)
                self.register_buffer("encoding", encoding.unsqueeze(0), persistent=False)

            def forward(self, x):
                return x + self.encoding[:, : x.size(1), :]

        class TransformerClassifier(nn.Module):
            def __init__(self):
                super().__init__()
                self.input_projection = nn.Linear(feature_count, hidden_size)
                self.position = PositionalEncoding()
                layer = nn.TransformerEncoderLayer(
                    d_model=hidden_size,
                    nhead=heads,
                    dim_feedforward=hidden_size * 4,
                    dropout=0.1,
                    batch_first=True,
                    activation="gelu",
                )
                self.encoder = nn.TransformerEncoder(layer, num_layers=layers)
                self.head = nn.Linear(hidden_size, 1)

            def forward(self, x):
                encoded = self.position(self.input_projection(x))
                encoded = self.encoder(encoded)
                return self.head(encoded[:, -1, :]).squeeze(-1)

        return TransformerClassifier()

    raise ValueError("model_type must be 'lstm' or 'transformer'")


def train_deep_sequence_model(
    train_samples: tuple[MLSample, ...] | list[MLSample],
    test_samples: tuple[MLSample, ...] | list[MLSample],
    *,
    model_type: ModelType = "lstm",
    sequence_length: int = 8,
    hidden_size: int = 32,
    layers: int = 1,
    heads: int = 4,
    epochs: int = 20,
    learning_rate: float = 1e-3,
    seed: int = 42,
) -> tuple[object, DeepLearningMetrics]:
    """Train chronologically and evaluate on later samples without leakage."""
    if model_type not in {"lstm", "transformer"}:
        raise ValueError("model_type must be 'lstm' or 'transformer'")
    if sequence_length < 2 or hidden_size < 1 or layers < 1 or heads < 1 or epochs < 1:
        raise ValueError("invalid deep-learning configuration")
    if learning_rate <= 0:
        raise ValueError("learning_rate must be > 0")

    train = _validate_samples(train_samples, "train_samples")
    test = _validate_samples(test_samples, "test_samples")
    if train[-1].index >= test[0].index:
        raise ValueError("train samples must strictly precede test samples")
    if len({sample.label for sample in train}) != 2:
        raise ValueError("training samples must contain both label classes")

    train_sequences: list[tuple[tuple[float, ...], ...]] = []
    train_labels: list[int] = []
    for position in range(sequence_length - 1, len(train)):
        window = train[position - sequence_length + 1 : position + 1]
        train_sequences.append(tuple(sample.features for sample in window))
        train_labels.append(train[position].label)
    if not train_sequences:
        raise ValueError("not enough training samples for sequence_length")

    test_sequences, test_labels = build_causal_sequences(
        train[-(sequence_length - 1):], test, sequence_length=sequence_length
    )
    if not test_sequences:
        raise ValueError("not enough test samples for sequence_length")

    torch, nn = _torch()
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    train_tensor, test_tensor, mean, std = _standardize(tuple(train_sequences), test_sequences)
    train_y = torch.tensor(train_labels, dtype=torch.float32)
    test_y = torch.tensor(test_labels, dtype=torch.float32)
    model = _make_model(model_type, len(train[0].features), sequence_length, hidden_size, layers, heads)

    positives = float(train_y.sum().item())
    negatives = float(len(train_y) - positives)
    pos_weight = torch.tensor([negatives / positives if positives else 1.0], dtype=torch.float32)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)

    model.train()
    final_loss = 0.0
    for _ in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        logits = model(train_tensor)
        loss = criterion(logits, train_y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        final_loss = float(loss.detach().item())

    model.eval()
    with torch.no_grad():
        scores = torch.sigmoid(model(test_tensor))
        predictions = (scores >= 0.5).to(torch.int64)
    labels_int = test_y.to(torch.int64)
    correct = int((predictions == labels_int).sum().item())
    true_positive = int(((predictions == 1) & (labels_int == 1)).sum().item())
    predicted_positive = int((predictions == 1).sum().item())
    actual_positive = int((labels_int == 1).sum().item())
    metrics = DeepLearningMetrics(
        model_type=model_type,
        train_samples=len(train_sequences),
        test_samples=len(test_sequences),
        sequence_length=sequence_length,
        feature_count=len(train[0].features),
        accuracy=correct / len(test_labels),
        positive_precision=true_positive / predicted_positive if predicted_positive else 0.0,
        positive_recall=true_positive / actual_positive if actual_positive else 0.0,
        final_train_loss=final_loss,
    )

    class ScoredModel:
        def __init__(self, fitted_model, normalization_mean, normalization_std):
            self._model = fitted_model
            self._mean = normalization_mean
            self._std = normalization_std

        def score(self, features_sequence):
            values = tuple(tuple(float(v) for v in row) for row in features_sequence)
            if len(values) != sequence_length or any(len(row) != len(train[0].features) for row in values):
                raise ValueError("features_sequence has incorrect shape")
            if any(not isfinite(value) for row in values for value in row):
                raise ValueError("features_sequence must be finite")
            tensor = torch.tensor([values], dtype=torch.float32)
            tensor = (tensor - self._mean) / self._std
            self._model.eval()
            with torch.no_grad():
                return float(torch.sigmoid(self._model(tensor)).item())

    return ScoredModel(model, mean, std), metrics


__all__ = [
    "ModelType",
    "DeepLearningMetrics",
    "build_causal_sequences",
    "train_deep_sequence_model",
]
