"""Behavior AI - the foundation feature (see PRD Phase 3). Not user-facing
itself: everything Commute AI, Schedule AI, and Chat AI's personalized
tier do reads from what this module computes. Deliberately deterministic
aggregation over Trip history, no LLM, same "transparent and debuggable"
posture as preference_engine.py.

Four signals, computed independently since each answers a different
question:

- feed accuracy: was the predicted_arrival right, for a given
  route/station/time-of-day slot? Validates the *data source*.
- direction choice: which route_or_direction did this user actually pick,
  at a given station and time-of-day slot? Validates *what to recommend
  this specific person*, independent of whether the feed was accurate.
- timing buffer: how long before predicted_arrival does this user
  actually start moving (leave home/office)? Feeds Schedule AI's "when to
  nudge" timing.
- typical predicted-arrival time: what clock time does this user's usual
  train/bus normally get predicted at, for a given station/slot? This is
  what turns "today's live predicted_arrival looks late" into an actual
  minutes-late NUMBER Schedule AI can honestly phrase as "leave N min
  later" - see typical_predicted_arrival_for_user's docstring for why this
  is a distinct question from feed_accuracy (which measures predicted-vs-
  actual error, not a same-day-comparable baseline clock time).

Time-of-day slotting uses a coarse 3-hour bucket (0-2, 3-5, ..., 21-23) -
fine enough to separate "AM rush" from "PM rush" without needing so many
buckets that any one of them starves for data given realistic trip
volumes. All signals below are None/omitted (never a fabricated number)
until _MIN_SAMPLES observations exist for that slot - an unconfident
guess is worse than an honest "not enough data yet," same principle as
preference_engine.py's transfer_aversion_score gap.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Trip

_MIN_SAMPLES = 3
_SLOT_HOURS = 3


def _time_slot(hour: int) -> int:
    return hour // _SLOT_HOURS


@dataclass(frozen=True)
class FeedAccuracy:
    mode: str
    origin_stop: str
    time_slot: int
    sample_count: int
    average_error_minutes: float


@dataclass(frozen=True)
class DirectionChoice:
    origin_stop: str
    time_slot: int
    sample_count: int
    most_common_route_or_direction: str
    confidence: float  # share of samples that picked most_common_route_or_direction


@dataclass(frozen=True)
class TimingBuffer:
    origin_stop: str
    time_slot: int
    sample_count: int
    average_buffer_minutes: float  # predicted_arrival - left_at, in minutes


@dataclass(frozen=True)
class TypicalArrivalTime:
    origin_stop: str
    time_slot: int
    sample_count: int
    # Average clock time (minutes since midnight UTC) that this station's
    # predicted_arrival has historically landed at, for this slot - the
    # baseline Schedule AI diffs today's live predicted_arrival against to
    # get a real minutes-late number. UTC, not local time - callers must
    # convert today's live predicted_arrival to the same UTC-minutes-since
    # -midnight basis before diffing, or the comparison is meaningless.
    average_minute_of_day_utc: float


def feed_accuracy_for_user(db: Session, user_id) -> list[FeedAccuracy]:
    """One entry per (mode, origin_stop, time_slot) with enough samples,
    per the PRD's "predicted vs. actual arrival time, per route/station/
    time-of-day" framing. Sign is preserved in nothing returned here - only
    the magnitude of the error, since "how far off" matters more than
    "early vs late" for the confidence framing this feeds (see
    llm_phrasing.py trust-preserving notes).
    """
    trips = db.scalars(
        select(Trip).where(
            Trip.user_id == user_id,
            Trip.predicted_arrival.isnot(None),
            Trip.actual_arrival.isnot(None),
        )
    ).all()

    groups: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for trip in trips:
        key = (trip.mode, trip.origin_stop, _time_slot(trip.start_time.hour))
        error_minutes = abs(
            (trip.actual_arrival - trip.predicted_arrival).total_seconds()
        ) / 60
        groups[key].append(error_minutes)

    results = []
    for (mode, origin_stop, time_slot), errors in groups.items():
        if len(errors) < _MIN_SAMPLES:
            continue
        results.append(
            FeedAccuracy(
                mode=mode,
                origin_stop=origin_stop,
                time_slot=time_slot,
                sample_count=len(errors),
                average_error_minutes=sum(errors) / len(errors),
            )
        )
    return results


def direction_choices_for_user(db: Session, user_id) -> list[DirectionChoice]:
    """One entry per (origin_stop, time_slot) with enough samples that have
    a captured route_or_direction. This is the signal Commute AI reads to
    infer "which direction is this person probably going" at a hub station
    - see the PRD's Commute AI description.
    """
    trips = db.scalars(
        select(Trip).where(
            Trip.user_id == user_id,
            Trip.route_or_direction.isnot(None),
        )
    ).all()

    groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    for trip in trips:
        key = (trip.origin_stop, _time_slot(trip.start_time.hour))
        groups[key].append(trip.route_or_direction)

    results = []
    for (origin_stop, time_slot), choices in groups.items():
        if len(choices) < _MIN_SAMPLES:
            continue
        counts = Counter(choices)
        winner, winner_count = counts.most_common(1)[0]
        results.append(
            DirectionChoice(
                origin_stop=origin_stop,
                time_slot=time_slot,
                sample_count=len(choices),
                most_common_route_or_direction=winner,
                confidence=winner_count / len(choices),
            )
        )
    return results


def timing_buffers_for_user(db: Session, user_id) -> list[TimingBuffer]:
    """One entry per (origin_stop, time_slot) with enough samples that have
    both predicted_arrival and left_at. Positive average_buffer_minutes
    means the user typically leaves before the predicted arrival (a real
    buffer); this can be negative if a user's real habit is to leave after
    a train's predicted time and still catch a later one - not clamped,
    since that's a real (if unusual) behavior pattern Schedule AI should
    still be able to read honestly rather than have it silently floored.
    """
    trips = db.scalars(
        select(Trip).where(
            Trip.user_id == user_id,
            Trip.predicted_arrival.isnot(None),
            Trip.left_at.isnot(None),
        )
    ).all()

    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    for trip in trips:
        key = (trip.origin_stop, _time_slot(trip.start_time.hour))
        buffer_minutes = (trip.predicted_arrival - trip.left_at).total_seconds() / 60
        groups[key].append(buffer_minutes)

    results = []
    for (origin_stop, time_slot), buffers in groups.items():
        if len(buffers) < _MIN_SAMPLES:
            continue
        results.append(
            TimingBuffer(
                origin_stop=origin_stop,
                time_slot=time_slot,
                sample_count=len(buffers),
                average_buffer_minutes=sum(buffers) / len(buffers),
            )
        )
    return results


def predict_direction(
    db: Session, user_id, origin_stop: str, hour: int
) -> DirectionChoice | None:
    """The one lookup Commute AI actually needs at request time: "given
    this station and this hour, what does this user usually do?" Returns
    None (never a guess) if there isn't enough history for this exact
    (origin_stop, time_slot) - callers must fall back to showing every
    direction unranked, per the PRD's explicit Commute AI fallback.
    """
    time_slot = _time_slot(hour)
    for choice in direction_choices_for_user(db, user_id):
        if choice.origin_stop == origin_stop and choice.time_slot == time_slot:
            return choice
    return None


def typical_arrival_times_for_user(db: Session, user_id) -> list[TypicalArrivalTime]:
    """One entry per (origin_stop, time_slot) with enough samples that have
    a predicted_arrival. Distinct from feed_accuracy_for_user, which
    measures |actual - predicted| (how far off the feed's OWN number
    turned out to be) - this instead answers "what predicted_arrival clock
    time is normal here," a same-day-comparable baseline. Schedule AI
    diffs today's live predicted_arrival against this to get a real
    minutes-late number ("your usual train is normally predicted around
    8:12, it's showing 8:27 today - that's a real ~15min delay"), not a
    guess - see the module docstring on why these are different questions.

    Averages minute-of-day naively (no midnight-wraparound handling) -
    safe here because every real predicted_arrival in this app's actual
    usage falls within normal daytime commute hours, never near midnight;
    documented so this isn't silently assumed to generalize to any
    time-of-day input.
    """
    trips = db.scalars(
        select(Trip).where(
            Trip.user_id == user_id,
            Trip.predicted_arrival.isnot(None),
        )
    ).all()

    groups: dict[tuple[str, int], list[float]] = defaultdict(list)
    for trip in trips:
        key = (trip.origin_stop, _time_slot(trip.start_time.hour))
        predicted = trip.predicted_arrival
        minute_of_day = predicted.hour * 60 + predicted.minute + predicted.second / 60
        groups[key].append(minute_of_day)

    results = []
    for (origin_stop, time_slot), minutes in groups.items():
        if len(minutes) < _MIN_SAMPLES:
            continue
        results.append(
            TypicalArrivalTime(
                origin_stop=origin_stop,
                time_slot=time_slot,
                sample_count=len(minutes),
                average_minute_of_day_utc=sum(minutes) / len(minutes),
            )
        )
    return results


def typical_arrival_time_for(
    db: Session, user_id, origin_stop: str, hour: int
) -> TypicalArrivalTime | None:
    """The one lookup Schedule AI actually needs at request time - same
    pattern as predict_direction. Returns None (never a guess) if there
    isn't enough history for this exact (origin_stop, time_slot).
    """
    time_slot = _time_slot(hour)
    for typical in typical_arrival_times_for_user(db, user_id):
        if typical.origin_stop == origin_stop and typical.time_slot == time_slot:
            return typical
    return None
