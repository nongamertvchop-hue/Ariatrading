"""Crash-safe persistence and recovery for the local order state machine.

The persistence layer stores only execution state. It never creates trading
signals and does not communicate with a broker. Writes use a temporary file and
an atomic replace so a process crash cannot intentionally overwrite the last
complete snapshot with a partially written JSON document.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile

from .order_state import OrderRecord, OrderState, OrderStateMachine


class OrderPersistenceError(RuntimeError):
    """Raised when an order-state snapshot cannot be safely loaded or stored."""


def _record_to_dict(record: OrderRecord) -> dict:
    payload = asdict(record)
    payload["state"] = record.state.value
    return payload


def save_order_state(machine: OrderStateMachine, path: str | os.PathLike[str]) -> None:
    """Atomically persist all order records as a versioned JSON snapshot."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "orders": [_record_to_dict(record) for record in machine.all_orders()],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))

    temp_name: str | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except OSError as exc:
        if temp_name is not None:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise OrderPersistenceError(f"failed to persist order state: {exc}") from exc


def load_order_state(path: str | os.PathLike[str]) -> OrderStateMachine:
    """Restore a validated order registry; malformed state fails closed."""
    target = Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrderPersistenceError(f"failed to load order state: {exc}") from exc

    if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("orders"), list):
        raise OrderPersistenceError("unsupported or malformed order-state snapshot")

    machine = OrderStateMachine()
    seen_client_ids: set[str] = set()
    seen_idempotency_keys: set[str] = set()
    for item in raw["orders"]:
        if not isinstance(item, dict):
            raise OrderPersistenceError("order snapshot contains a non-object record")
        required = {"client_order_id", "idempotency_key", "direction", "quantity", "state"}
        if not required.issubset(item):
            raise OrderPersistenceError("order snapshot record is missing required fields")
        try:
            client_order_id = str(item["client_order_id"])
            idempotency_key = str(item["idempotency_key"])
            if client_order_id in seen_client_ids or idempotency_key in seen_idempotency_keys:
                raise OrderPersistenceError("duplicate order identity in snapshot")
            seen_client_ids.add(client_order_id)
            seen_idempotency_keys.add(idempotency_key)

            quantity = float(item["quantity"])
            state = OrderState(str(item["state"]))
            broker_id = item.get("broker_order_id")
            filled = float(item.get("filled_quantity", 0.0))
            machine.restore(
                OrderRecord(
                    client_order_id=client_order_id,
                    idempotency_key=idempotency_key,
                    direction=str(item["direction"]),
                    quantity=quantity,
                    state=state,
                    broker_order_id=None if broker_id is None else str(broker_id),
                    filled_quantity=filled,
                )
            )
        except OrderPersistenceError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            raise OrderPersistenceError("invalid order snapshot field") from exc

    return machine
