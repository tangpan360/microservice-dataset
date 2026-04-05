from __future__ import annotations

from locust import LoadTestShape

from tt_injector.config.models import MixConfig, PhaseConfig


class PhaseLoadShape(LoadTestShape):
    abstract = True
    mix_config: MixConfig | None = None

    def tick(self):
        if self.mix_config is None:
            return None
        run_time = self.get_run_time()
        elapsed = 0
        for phase in self.mix_config.phases:
            phase_seconds = phase.duration_min * 60
            elapsed += phase_seconds
            if run_time < elapsed:
                users = phase.users if phase.users is not None else 1
                spawn_rate = phase.spawn_rate if phase.spawn_rate is not None else max(1, users)
                return users, spawn_rate
        return None


def phase_for_runtime(mix_config: MixConfig, run_time_sec: float) -> PhaseConfig | None:
    elapsed = 0
    for phase in mix_config.phases:
        elapsed += phase.duration_min * 60
        if run_time_sec < elapsed:
            return phase
    return None
