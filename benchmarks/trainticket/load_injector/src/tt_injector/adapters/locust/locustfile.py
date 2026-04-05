from __future__ import annotations

import os
import time

from locust import User, constant, events, task

from tt_injector.adapters.locust.shapes import PhaseLoadShape, phase_for_runtime
from tt_injector.adapters.locust.tasks import choose_scenario_id, run_scenario
from tt_injector.config.loader import load_mix_config
from tt_injector.core.context import RuntimeContext
from tt_injector.scenarios.runtime import ScenarioRuntime

MIX_CONFIG_PATH = os.environ.get("TT_MIX_CONFIG", "configs/mix/steady.yaml")
MIX_CONFIG = load_mix_config(MIX_CONFIG_PATH)
TEST_STARTED_AT: float | None = None


@events.init_command_line_parser.add_listener
def add_parser_arguments(parser):
    parser.add_argument("--tt-mix-config", type=str, env_var="TT_MIX_CONFIG", default=MIX_CONFIG_PATH)


@events.test_start.add_listener
def record_test_start(environment, **kwargs):
    global TEST_STARTED_AT
    TEST_STARTED_AT = time.time()


class TrainTicketShape(PhaseLoadShape):
    mix_config = MIX_CONFIG


class TrainTicketUser(User):
    wait_time = constant(0)

    def on_start(self):
        self.context = RuntimeContext()
        self.runtime = ScenarioRuntime.create(self.context)
        self.rng = self.context.new_rng()

    def _current_phase(self):
        if TEST_STARTED_AT is None:
            return MIX_CONFIG.phases[0] if MIX_CONFIG.phases else None
        run_time = time.time() - TEST_STARTED_AT
        return phase_for_runtime(MIX_CONFIG, run_time)

    @task
    def run_mix(self):
        phase = self._current_phase()
        if phase is None:
            return
        scenario_id = choose_scenario_id(phase.mix, self.rng)
        started = time.perf_counter()
        try:
            result = run_scenario(self.runtime, scenario_id, self.rng)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            events.request.fire(
                request_type="scenario",
                name=scenario_id,
                response_time=elapsed_ms,
                response_length=0,
                exception=None if result.ok else RuntimeError(result.detail or f"{scenario_id} failed"),
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            events.request.fire(
                request_type="scenario",
                name=scenario_id,
                response_time=elapsed_ms,
                response_length=0,
                exception=exc,
            )
            self.runtime = ScenarioRuntime.create(self.context)
