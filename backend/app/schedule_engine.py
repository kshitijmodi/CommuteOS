"""Schedule AI (see PRD Phase 3) - owns only the timing question: when
should this user leave, and is today's routine disrupted enough to say
something about it. Deterministic, no LLM in the decision path - same
"transparent and debuggable" posture as every other engine module.
Routing (which route/mode is best) is NOT this module's job; when a
disruption forces a substitute, this module hands the real candidates to
decision_engine.rank_routes (the same scorer recommendation_builder.py
already uses) rather than re-implementing route-picking - see the PRD's
"Schedule AI delegates to Commute AI's engine" framing. Commute AI itself
doesn't exist as a separate module yet (build order: Schedule AI before
Commute AI), so "delegates" today means "calls the one ranking function
that exists," which remains true once Commute AI is built - it will call
the same function, not a new one.

Two things this module answers:

1. usual_departure_hour_for: what hour does this user typically start a
   morning (home) or evening (office) trip? Mirrors home_office_engine's
   noon-cutoff morning/evening split but resolves to an HOUR, not just
   which slot - the actual signal the notification job's timing needs.
2. classify_disruption: given today's live predicted_arrival and
   Behavior AI's typical_arrival_time_for baseline, is this user's usual
   route on time, meaningfully delayed, or is there no live data at all
   (the "usual route may not be running" case)? A real minutes-late
   number, not a guess - see behavior_engine.typical_arrival_time_for's
   docstring on why this is the honest signal to diff against, not a
   fabricated "recent delay variance."
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from .behavior_engine import typical_arrival_time_for
from .models import Trip

_MIN_TRIPS_FOR_DEPARTURE_HOUR = 3
_NOON_HOUR = 12

# A delay under this many minutes reads as "basically on time" rather
# than worth calling out - small feed jitter (a minute or two) shouldn't
# trigger a "your train is delayed" message that erodes trust the first
# time it's wrong by a rounding error. Chosen as a round, explainable
# number, not tuned against real data (none exists yet to tune against).
_ON_TIME_TOLERANCE_MINUTES = 3

# How many hours ahead of a user's usual departure hour the job should
# notify them - the job runs hourly (see OPEN_QUESTIONS.md on why not
# tighter), so this is also effectively the notification window's width.
_LEAD_HOURS = 1


class DisruptionSeverity(Enum):
    ON_TIME = "on_time"
    DELAYED = "delayed"
    NO_LIVE_DATA = "no_live_data"


@dataclass(frozen=True)
class DisruptionAssessment:
    severity: DisruptionSeverity
    # None for NO_LIVE_DATA (nothing to measure), or when no typical
    # -arrival baseline exists yet for this station/slot (too new a user -
    # can't call something "delayed" relative to a baseline that doesn't
    # exist, so this degrades to ON_TIME rather than a fabricated severity).
    delay_minutes: float | None


def usual_departure_hour_for(db: Session, user_id, is_morning: bool) -> int | None:
    """Most common Trip.start_time hour among this user's morning (or
    evening) trips - same noon-cutoff split home_office_engine.py already
    uses, resolved to an hour rather than just a home/office station.
    Returns None (never a guess) below _MIN_TRIPS_FOR_DEPARTURE_HOUR.
    """
    trips = db.scalars(select(Trip).where(Trip.user_id == user_id)).all()
    matching = [
        t
        for t in trips
        if (t.start_time.hour < _NOON_HOUR) == is_morning
    ]
    if len(matching) < _MIN_TRIPS_FOR_DEPARTURE_HOUR:
        return None

    hours = Counter(t.start_time.hour for t in matching)
    return hours.most_common(1)[0][0]


def is_within_notification_window(now_hour: int, usual_departure_hour: int) -> bool:
    """True when now_hour is _LEAD_HOURS before usual_departure_hour - the
    job should notify a user AHEAD of their usual departure, not at or
    after it (per the PRD: "fires... ahead of the user's usual departure
    window"). Both hours are plain 0-23 UTC hours; callers are responsible
    for using the same hour basis on both sides (see
    send_commute_notifications.py, which uses datetime.now(timezone.utc)
    consistently throughout - this app is NYC-metro-only today, see
    OPEN_QUESTIONS.md, so a real per-user timezone isn't yet a concern).
    """
    return now_hour == (usual_departure_hour - _LEAD_HOURS) % 24


def classify_disruption(
    live_predicted_arrival: datetime, typical_minute_of_day_utc: float | None
) -> DisruptionAssessment:
    """Compares today's live predicted_arrival against Behavior AI's
    learned baseline for this station/slot. No baseline yet (too little
    history) degrades to ON_TIME rather than inventing a severity - an
    honest "nothing to compare against" is not the same claim as "this is
    normal," but reporting ON_TIME (i.e. staying quiet about a possible
    delay this module genuinely cannot assess) is the safer default than
    fabricating a DELAYED verdict with no real baseline behind it.
    """
    if typical_minute_of_day_utc is None:
        return DisruptionAssessment(severity=DisruptionSeverity.ON_TIME, delay_minutes=None)

    live_utc = live_predicted_arrival.astimezone(timezone.utc)
    live_minute_of_day = live_utc.hour * 60 + live_utc.minute + live_utc.second / 60
    delay_minutes = live_minute_of_day - typical_minute_of_day_utc

    if delay_minutes <= _ON_TIME_TOLERANCE_MINUTES:
        return DisruptionAssessment(severity=DisruptionSeverity.ON_TIME, delay_minutes=delay_minutes)
    return DisruptionAssessment(severity=DisruptionSeverity.DELAYED, delay_minutes=delay_minutes)


def assess_candidate(
    db: Session, user_id, origin_stop: str, hour: int, live_predicted_arrival: datetime | None
) -> DisruptionAssessment:
    """The one lookup the notification job actually needs at request
    time: given a candidate's real live predicted_arrival (or None if the
    live fetch came back with nothing for it - the NO_LIVE_DATA case),
    how disrupted does this look relative to what's normal for this user?
    """
    if live_predicted_arrival is None:
        return DisruptionAssessment(severity=DisruptionSeverity.NO_LIVE_DATA, delay_minutes=None)

    typical = typical_arrival_time_for(db, user_id, origin_stop, hour)
    typical_minute = typical.average_minute_of_day_utc if typical else None
    return classify_disruption(live_predicted_arrival, typical_minute)
