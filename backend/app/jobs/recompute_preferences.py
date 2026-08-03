"""Standalone entrypoint for the PRD's nightly preference-recompute job.
Also runs home/office inference (same nightly-job-stand-in pattern - see
home_office_engine.py) since both derive from the same Trip history.

Can be run manually (`python -m app.jobs.recompute_preferences`) or, in
production, is triggered nightly via POST
/internal/run-preference-recompute-job (see routers/internal.py) by a
scheduled GitHub Actions workflow - the same pattern used for the
commute-notification job, since Render's free tier has no cron and the
service sleeps when idle.
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
