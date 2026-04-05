from __future__ import annotations

import argparse

from tt_injector.core.context import RuntimeContext
from tt_injector.registry.scenarios import SCENARIOS
from tt_injector.scenarios.runtime import ScenarioRuntime


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one scenario without Locust.")
    parser.add_argument("scenario_id", choices=sorted(SCENARIOS))
    args = parser.parse_args()

    context = RuntimeContext()
    runtime = ScenarioRuntime.create(context)
    rng = context.new_rng()
    result = SCENARIOS[args.scenario_id].handler(runtime, rng)
    print({"scenario_id": args.scenario_id, "ok": result.ok, "detail": result.detail, "payload": result.payload})
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
