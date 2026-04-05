from __future__ import annotations

from random import Random

from tt_injector.registry.scenarios import SCENARIOS
from tt_injector.scenarios.runtime import ScenarioRuntime


def normalize_mix(mix: dict[str, float]) -> list[tuple[str, float]]:
    total = sum(mix.values())
    if total <= 0:
        raise ValueError("mix 权重总和必须大于 0")
    return [(scenario_id, weight / total) for scenario_id, weight in mix.items()]


def choose_scenario_id(mix: dict[str, float], rng: Random) -> str:
    normalized = normalize_mix(mix)
    cursor = 0.0
    probe = rng.random()
    for scenario_id, weight in normalized:
        cursor += weight
        if probe <= cursor:
            return scenario_id
    return normalized[-1][0]


def run_scenario(runtime: ScenarioRuntime, scenario_id: str, rng: Random):
    spec = SCENARIOS[scenario_id]
    return spec.handler(runtime, rng)
