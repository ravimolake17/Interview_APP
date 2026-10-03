"""Standalone screening worker process for horizontal scaling on Azure."""

from __future__ import annotations

import asyncio
import logging
import signal

from agents.screening_agent.config import settings
from agents.screening_agent.services.screening_worker_pool import ScreeningWorkerPool

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


async def _run() -> None:
    pool = ScreeningWorkerPool()
    await pool.start()
    logger.info(
        "Standalone screening worker running (%d workers). Press Ctrl+C to stop.",
        settings.MAX_CONCURRENT_SCREENING_JOBS,
    )

    stop_event = asyncio.Event()

    def _request_stop(*_args) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, _request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _request_stop)

    await stop_event.wait()
    await pool.stop()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
