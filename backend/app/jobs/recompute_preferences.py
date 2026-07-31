"""Standalone entrypoint for the PRD's nightly preference-recompute job.
Also runs home/office inference (same nightly-job-stand-in pattern - see
home_office_engine.py) since both derive from the same Trip history.

Run manually for now (`python -m app.jobs.recompute_preferences`); wiring
this to an actual OS-level scheduler (cron / Windows Task Scheduler / a
hosted cron service) is a deployment concern, tracked in
OPEN_QUESTIONS.md alongside backend hosting - not solved here, since it
depends on where this ends up running.
"""

from ..core.database import SessionLocal
from ..home_office_engine import infer_home_and_office_for_all_users
from ..preference_engine import recompute_all_preferences


def main() -> None:
    db = SessionLocal()
    try:
        pref_count = recompute_all_preferences(db)
        print(f"Recomputed preferences for {pref_count} user(s).")
        home_office_count = infer_home_and_office_for_all_users(db)
        print(f"Inferred home/office for {home_office_count} user(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
