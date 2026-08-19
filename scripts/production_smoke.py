#!/usr/bin/env python3
"""Opt-in API v2 production smoke test.

This script consumes one Token Portal use. It does nothing unless the explicit
confirmation flag and DANDELIION_API_TOKEN are both provided.
"""

# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from dandeliion.client import Simulator


def main() -> int:
    """Run the explicitly acknowledged production API contract check."""
    parser = argparse.ArgumentParser()
    parser.add_argument("parameters", type=Path, help="BPX JSON submission body")
    parser.add_argument("--api-url", default="https://api.dandeliion.com")
    parser.add_argument("--output", type=Path, default=Path("solution-v2.json"))
    parser.add_argument(
        "--confirm-consume-use",
        action="store_true",
        help="Required acknowledgement that this command consumes one Token Portal use",
    )
    args = parser.parse_args()
    if not args.confirm_consume_use:
        parser.error("--confirm-consume-use is required because this test consumes one use")
    token = os.environ.get("DANDELIION_API_TOKEN")
    if not token:
        parser.error("DANDELIION_API_TOKEN is required")

    parameters = json.loads(args.parameters.read_text())
    simulator = Simulator(args.api_url, token)
    idempotency_key = f"client-smoke-{uuid.uuid4()}"
    solution = simulator.submit(
        parameters,
        is_blocking=False,
        idempotency_key=idempotency_key,
    )
    replay = simulator.submit(
        parameters,
        is_blocking=False,
        idempotency_key=idempotency_key,
    )
    if replay.run_id != solution.run_id:
        raise RuntimeError("Idempotent replay returned a different run")

    solution.join()
    if solution.status != "succeeded":
        raise RuntimeError(f"Smoke run ended in {solution.status}: {solution.log}")
    fields = list(solution)
    selected = next((field for field in fields if field != "Time [s]"), fields[0])
    _ = solution[selected]
    _ = solution.log
    solution.dump(args.output)
    restored = Simulator.restore(args.output)
    _ = restored[selected]
    print(f"API v2 smoke test passed for run {solution.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
