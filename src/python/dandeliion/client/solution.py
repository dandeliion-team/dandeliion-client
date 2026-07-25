"""Dictionary-style access to a DandeLiion simulation solution."""

# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

import ijson
import numpy as np
import numpy.typing as npt

from .exceptions import DandeliionAPIException
from .token import TokenValidation


class Simulator(Protocol):
    """Internal protocol implemented by the API transport."""

    def _get_status(self, solution: Solution) -> str: ...

    def _get_log(self, solution: Solution) -> str: ...

    def _fetch_fields(self, solution: Solution, fields: list[str]) -> dict[str, np.ndarray]: ...

    def _join(self, solution: Solution, timeout: float | None = None) -> None: ...

    def _cancel(self, solution: Solution) -> str: ...

    def _dump(self, solution: Solution, filepath: str | Path) -> None: ...


class InterpolatedArray(np.ndarray):
    """An ndarray that supports linear interpolation when called."""

    t: np.ndarray | None

    def __new__(
        cls,
        t: npt.ArrayLike,
        y: npt.ArrayLike,
        **kwargs: Any,
    ) -> InterpolatedArray:
        time_values = np.asarray(t)
        values = np.array(y, copy=True, **kwargs)
        if time_values.ndim != 1 or values.ndim != 1:
            raise ValueError("x and y must be one-dimensional array-like objects")
        if time_values.shape != values.shape:
            raise ValueError("x and y must have the same length")
        instance = values.view(cls)
        instance.t = np.array(time_values, copy=True)
        return instance

    def __array_finalize__(self, obj: np.ndarray | None) -> None:
        self.t = getattr(obj, "t", None)

    def __getitem__(self, key: Any) -> Any:
        result = super().__getitem__(key)
        if isinstance(result, InterpolatedArray) and self.t is not None and self.ndim == 1 and self.t.ndim == 1:
            sliced_time = self.t[key]
            result.t = np.array(sliced_time, copy=True) if np.ndim(sliced_time) == 1 else None
        return result

    def __call__(self, t: npt.ArrayLike) -> np.ndarray:
        if self.t is None:
            raise ValueError("Interpolation metadata is not available")
        if self.t.ndim != 1 or self.ndim != 1:
            raise ValueError("x and y must be one-dimensional array-like objects")
        if self.t.shape != self.shape:
            raise ValueError("x and y must have the same length")
        query = np.asarray(t, dtype=float)
        return np.interp(query, self.t, np.asarray(self))


class Solution(Mapping[str, np.ndarray]):
    """A mapping that lazily fetches and caches simulation result fields."""

    def __init__(
        self,
        sim: Simulator,
        run: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        log: str = "",
        log_offset: int = 0,
        bundle_path: Path | None = None,
        local_result: bool = False,
        time_column: str | None = None,
    ):
        self._sim = sim
        self._run = run
        self._idempotency_key = idempotency_key
        self._log = log
        self._log_offset = log_offset
        self._bundle_path = bundle_path
        self._local_result = local_result
        self._time_column = time_column
        self._fields: dict[str, np.ndarray] = {}

    @property
    def run_id(self) -> str:
        """Return the UUID of the API run."""
        return self._run["id"]

    @property
    def idempotency_key(self) -> str | None:
        """Return the key used for the original submission, when known."""
        return self._idempotency_key

    def _set_run(self, run: dict[str, Any]) -> None:
        self._run = run

    def _available_fields(self) -> list[str]:
        if self._run["status"] not in {"succeeded", "failed", "cancelled", "timed_out"}:
            self._sim._get_status(self)
        if self._run["status"] != "succeeded":
            message = self._run.get("error_message") or "Solution not ready."
            raise DandeliionAPIException(
                message,
                code=self._run.get("error_code") or "result_not_available",
            )
        fields = self._run["artifacts"]["solution_fields"]
        if not isinstance(fields, list):
            raise DandeliionAPIException("Run metadata contains invalid solution fields.")
        return fields

    def _read_local_fields(self, fields: list[str]) -> dict[str, np.ndarray]:
        if self._bundle_path is None or not self._local_result:
            return {}
        found: dict[str, np.ndarray] = {}
        try:
            with self._bundle_path.open("rb") as handle:
                for key, value in ijson.kvitems(
                    handle,
                    "result.Solution",
                    use_float=True,
                ):
                    if key in fields and key not in found:
                        if not isinstance(value, list):
                            raise DandeliionAPIException(f"The restore bundle field '{key}' is not a JSON array.")
                        array = np.asarray(value)
                        if array.ndim < 1 or not np.issubdtype(array.dtype, np.number):
                            raise DandeliionAPIException(f"The restore bundle field '{key}' is not a numeric array.")
                        found[key] = array
                        if len(found) == len(fields):
                            break
        except (OSError, ijson.JSONError, UnicodeError, TypeError, ValueError) as exc:
            raise DandeliionAPIException("The restore bundle contains invalid solution data.") from exc
        if set(found) != set(fields):
            missing = ", ".join(field for field in fields if field not in found)
            raise DandeliionAPIException(f"The restore bundle omits solution fields: {missing}.")
        return found

    def _load_fields(self, fields: list[str]) -> None:
        pending = [field for field in fields if field not in self._fields]
        if not pending:
            return
        if self._local_result:
            loaded = self._read_local_fields(pending)
        else:
            loaded = self._sim._fetch_fields(self, pending)
        self._fields.update(loaded)

    def __getitem__(self, key: str) -> np.ndarray:
        available = self._available_fields()
        if key not in available:
            raise KeyError(f"Column for {key} does not exist in solution.")
        requested: list[str] = []
        if self._time_column is not None and self._time_column not in self._fields and self._time_column in available:
            requested.append(self._time_column)
        if key not in requested and key not in self._fields:
            requested.append(key)
        self._load_fields(requested)
        if self._time_column is not None:
            if self._time_column not in self._fields:
                raise DandeliionAPIException(
                    f"Solution does not contain the required time field '{self._time_column}'."
                )
            time_values = self._fields[self._time_column]
            values = self._fields[key]
            if time_values.ndim == 1 and values.ndim == 1 and time_values.shape == values.shape:
                return InterpolatedArray(t=time_values, y=values)
            return np.array(values, copy=True)
        return np.array(self._fields[key], copy=True)

    def __len__(self) -> int:
        return len(self._available_fields())

    def __iter__(self):
        yield from self._available_fields()

    @property
    def status(self) -> str:
        """Return the current API v2 run state."""
        return self._sim._get_status(self)

    @property
    def log(self) -> str:
        """Return all runtime log text retrieved so far."""
        return self._sim._get_log(self)

    @property
    def token_validation(self) -> TokenValidation | None:
        """Return the point-in-time Token Portal validation metadata."""
        payload = self._run.get("portal_validation")
        if not payload:
            return None
        try:
            return TokenValidation.from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise DandeliionAPIException("Run metadata contains invalid token validation data.") from exc

    def dump(self, filepath: str | Path) -> None:
        """Atomically write a versioned, restorable solution bundle."""
        self._sim._dump(self, filepath)

    def join(self, timeout: float | None = None) -> None:
        """Wait until the run reaches any terminal state."""
        self._sim._join(self, timeout)

    def cancel(self) -> str:
        """Request idempotent cancellation and return the updated run state."""
        return self._sim._cancel(self)
