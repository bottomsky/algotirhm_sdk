"""Measure JSON and executor overhead for synthetic complete scenarios."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from algo_sdk import (  # noqa: E402
    AlgorithmRequest, AlgorithmSpec, AlgorithmType, BaseAlgorithm, BaseModel,
    ExecutionConfig, ExecutionRequest, InProcessExecutor, ProcessPoolExecutor,
    get_current_raw_data,
)


class Input(BaseModel):
    value: int


class Output(BaseModel):
    satellites: int


class CountAlgorithm(BaseAlgorithm[Input, Output]):
    def run(self, req: Input) -> Output:
        raw = get_current_raw_data()
        return Output(satellites=(
            len(raw["force"]["equipment"]) if raw is not None else 0
        ))


def scenario(count: int) -> dict:
    return {
        "id": "synthetic", "scenario": {"sceneId": 1},
        "force": {"equipment": [{
            "uuid": str(index), "forceSide": index % 2 + 1,
            "equipmentParam": {
                "platParam": {
                    "satMass": 100, "customPower": 250,
                    "orbitElem": {"ecc": 0.01, "sMajAx": 7000000},
                    "dynamicConfig": {"enabled": True, "gains": [1, 2, 3]},
                },
                "payloadParams": [{"customPayload": {
                    "type": number, "values": list(range(20)),
                    "extra": {"modes": ["a", "b"], "optional": None},
                }} for number in range(6)],
            },
        } for index in range(count)]},
    }


def median_ms(action, iterations: int) -> float:
    samples = []
    for _ in range(iterations):
        start = perf_counter()
        action()
        samples.append((perf_counter() - start) * 1000)
    return round(statistics.median(samples), 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--satellites", nargs="+", type=int, default=[100, 1000])
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    if args.iterations < 1 or any(count < 1 for count in args.satellites):
        parser.error("satellites and iterations must be positive")
    spec = AlgorithmSpec(
        name="raw_benchmark", version="v1", description="synthetic overhead",
        created_time="2026-11-13", author="qa", category="benchmark",
        application_scenarios="test", input_model=Input, output_model=Output,
        algorithm_type=AlgorithmType.PREDICTION, execution=ExecutionConfig(),
        entrypoint=CountAlgorithm, is_class=True,
    )
    in_process = InProcessExecutor()
    pool = ProcessPoolExecutor(max_workers=1)
    results = []
    try:
        for count in args.satellites:
            envelope = AlgorithmRequest(
                requestId="benchmark", datetime=datetime.now(timezone.utc),
                data={"value": 1}, rawData=scenario(count),
            )
            encoded = envelope.model_dump_json()
            request = ExecutionRequest(
                spec=spec, payload=envelope.data, request_id="benchmark",
                raw_data=envelope.rawData,
            )

            def invoke(executor) -> None:
                result = executor.submit(request)
                assert result.success, result.error
                assert result.data.satellites == count

            # Exclude worker startup from the steady-state measurements.
            invoke(in_process)
            invoke(pool)
            results.append({
                "satellites": count,
                "payload_bytes": len(encoded.encode()),
                "json_decode_ms": median_ms(
                    lambda: json.loads(encoded), args.iterations,
                ),
                "envelope_parse_ms": median_ms(
                    lambda: AlgorithmRequest.model_validate_json(encoded),
                    args.iterations,
                ),
                "in_process_ms": median_ms(
                    lambda: invoke(in_process), args.iterations,
                ),
                "process_pool_ms": median_ms(
                    lambda: invoke(pool), args.iterations,
                ),
            })
    finally:
        in_process.shutdown()
        pool.shutdown()
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
