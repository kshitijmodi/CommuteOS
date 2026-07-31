"""Standalone entrypoint for the PRD's nightly preference-recompute job.

Run manually for now (`python -m app.jobs.recompute_preferences`); wiring
this to an actual OS-level scheduler (cron / Windows Task Scheduler / a
hosted cron service) is a deployment concern, tracked in
OPEN_QUESTIONS.md alongside backend hosting - not solved here, since it
depends on where this ends up running.
"""

from ..core.database import SessionLocal
from ..preference_engine import recompute_all_preferences


def main() -> None:
    db = SessionLocal()
    try:
        count = recompute_all_preferences(db)
        print(f"Recomputed preferences for {count} user(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
