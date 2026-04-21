"""
Standalone cron job runner.

Called by system cron inside the Docker container:
    python -m app.shared.cron.runner <job_name>

Imports the registered job function, runs it, then exits.
Designed to be stateless — connects to DB, does work, exits cleanly.

Usage:
    python -m app.shared.cron.runner billing_renewal
    python -m app.shared.cron.runner --list
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cron:%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("cron.runner")


def _import_func(dotted_path: str):
    """Import a function from a dotted path like 'app.module.func'."""
    module_path, func_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


async def _run_job(job_name: str) -> None:
    from app.shared.cron.registry import get_job

    job = get_job(job_name)
    if not job:
        logger.error("Unknown cron job: %s", job_name)
        sys.exit(1)

    logger.info("Starting cron job: %s — %s", job.name, job.description)
    start = time.monotonic()

    try:
        # Ensure all models are registered so SQLAlchemy can resolve FK references
        import app.modules.tenants.models  # noqa: F401
        import app.modules.users.models  # noqa: F401
        import app.modules.billing.models  # noqa: F401

        func = _import_func(job.func)
        result = await func()
        elapsed = time.monotonic() - start
        logger.info("Cron job %s completed in %.1fs — result: %s", job.name, elapsed, result)
    except Exception:
        elapsed = time.monotonic() - start
        logger.exception("Cron job %s failed after %.1fs", job.name, elapsed)
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.shared.cron.runner <job_name>")
        print("       python -m app.shared.cron.runner --list")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--list":
        from app.shared.cron.registry import list_jobs
        for job in list_jobs():
            print(f"  {job.name:<25} {job.schedule:<15} {job.description}")
        return

    asyncio.run(_run_job(arg))


if __name__ == "__main__":
    main()
