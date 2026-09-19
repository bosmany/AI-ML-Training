"""Application factory (scaffold - provided, do not edit).

Every call builds a NEW monitor, a NEW Prometheus ``CollectorRegistry`` and a NEW app: no module-level globals, so
two apps (or two tests) never collide with "Duplicated timeseries" errors or share state.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import FastAPI

from lab import api
from lab.config import MonitorConfig
from lab.metrics import DriftMetrics
from lab.monitor import DriftMonitor


def create_app(config: MonitorConfig, *, timer: Callable[[], float] = time.perf_counter) -> FastAPI:
    app = FastAPI(title="Drift monitor", version="1.0.0")
    app.state.monitor = DriftMonitor(config)
    app.state.metrics = DriftMetrics()  # its own CollectorRegistry
    app.state.timer = timer  # injectable so tests can assert the latency histogram without sleeping
    app.include_router(api.router)
    return app
