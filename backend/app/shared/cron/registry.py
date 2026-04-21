"""
Generic cron job registry.

Any module can register a cron job by adding an entry to CRON_JOBS.
The crontab file and runner script use this registry to discover jobs.

Usage:
    1. Define an async function: async def my_job() -> None
    2. Register it in CRON_JOBS below
    3. Add a crontab entry: * * * * * cd /app && python -m app.shared.cron.runner my_job_name

Each job is a dict with:
    - name:        Unique identifier (used as CLI argument)
    - func:        Dotted import path to an async function
    - schedule:    Cron expression (for documentation / crontab generation)
    - description: Human-readable description
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CronJob:
    name: str
    func: str          # e.g. "app.modules.billing.renewal_service.process_renewals"
    schedule: str      # e.g. "0 * * * *"  (every hour)
    description: str


# ━━━ Register all cron jobs here ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRON_JOBS: list[CronJob] = [
    CronJob(
        name="billing_renewal",
        func="app.modules.billing.renewal_service.process_renewals",
        schedule="0 * * * *",
        description="Check for expired subscriptions and attempt auto-renewal",
    ),
]


def get_job(name: str) -> CronJob | None:
    return next((j for j in CRON_JOBS if j.name == name), None)


def list_jobs() -> list[CronJob]:
    return CRON_JOBS
