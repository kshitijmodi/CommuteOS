"""Phase 3 LLM phrasing layer. Per the PRD, the LLM's job is narrow and
specific: take the decision engine's structured output and phrase it as a
sentence - it never sees raw trip history, never picks the route itself,
and is never asked to invent a number that isn't already in the input.
This is the highest-risk-of-hallucination surface in the whole system
(inventing a departure time has a real consequence - a missed train), so
the prompt is deliberately narrow and the temperature is low.

Uses the real Anthropic API (claude-sonnet-5) - switched from Groq
(llama-3.1-8b-instant) 2026-08-19 after that model was found to be fully
decommissioned (Groq's API returned "model_not_found" on a direct call).
This had been silently invisible for at least ~2.5 weeks because of the
very fail-soft design described below - every phrased answer had quietly
been template-only that whole time, with no visible error anywhere. This
is a real Anthropic API key (console.anthropic.com, billed per-token) -
NOT the same credential as a claude.ai Pro/Team subscription login,
which has no supported way to authenticate server-side backend calls at
all.

Fails soft, not hard: if no API key is configured or the call errors, this
falls back to a deterministic template (see _template_phrase) instead of
raising - a recommendation with slightly worse prose beats no
recommendation at all, and this is explicitly a "nice to have" layer per
the PRD (phrasing only, never the decision).
"""

from typing import TYPE_CHECKING

from anthropic import Anthropic, AnthropicError

from .core.config import settings
from .decision_engine import RankedRoute
from .schedule_engine import DisruptionAssessment, DisruptionSeverity

if TYPE_CHECKING:
    # Import-time only, never at runtime - commute_engine.py imports
    # recommendation_builder.py, which imports THIS module, so a real
    # top-level import here would be a circular import. TYPE_CHECKING
    # guards keep the type hint below without ever executing the import.
    from .commute_engine import CommuteRecommendation


def _extract_text(response) -> str | None:
    """response.content is a list of blocks, not a single message the
    way the old OpenAI-shaped response was - claude-sonnet-5 in
    particular can return a "thinking" block ahead of the real "text"
    block, so content[0] can't be assumed to be it. Shared by every
    phrase_* function below rather than duplicated four times."""
    text = next((block.text for block in response.content if block.type == "text"), None)
    return text.strip() if text else None

_SYSTEM_PROMPT = """You are a transit assistant. You will be given a single \
JSON object describing one recommended route: mode, label, predicted \
arrival time, and a confidence score between 0 and 1.

Write ONE short sentence (under 200 characters) telling the commuter what \
to do, in a natural, direct tone.

Rules you must never break:
- Only use the numbers/times given to you. Never invent, adjust, or round \
a time in a way that changes its meaning.
- Reflect the given confidence honestly - do not sound more certain than \
the confidence score warrants. Confidence below 0.6 should sound hedged \
("looks like", "should").
- Do not mention "confidence" or "score" as words - translate them into \
natural certainty in your tone instead.
- Output only the sentence, no preamble, no quotes around it."""


def phrase_recommendation(route: RankedRoute) -> str:
    if not settings.anthropic_api_key:
        return _template_phrase(route)

    client = Anthropic(api_key=settings.anthropic_api_key)

    payload = {
        "mode": route.mode,
        "label": route.label,
        "predicted_arrival": route.predicted_arrival.isoformat(),
        "confidence": round(route.confidence, 2),
    }

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            system=_SYSTEM_PROMPT,
            max_tokens=100,
            messages=[{"role": "user", "content": str(payload)}],
        )
        text = _extract_text(response)
        return text if text else _template_phrase(route)
    except AnthropicError:
        return _template_phrase(route)


def _template_phrase(route: RankedRoute) -> str:
    time_str = route.predicted_arrival.strftime("%I:%M %p").lstrip("0")
    hedge = "should" if route.confidence >= 0.6 else "might"
    return f"Your {route.label} {hedge} arrive around {time_str}."


_COMPARISON_SYSTEM_PROMPT = """You are a transit assistant. You will be given \
a JSON object with a "winner" (the recommended route) and an "alternatives" \
list (every other option that was considered), each with mode, label, \
predicted arrival time, and a confidence score between 0 and 1. The winner \
was already chosen by a separate scoring system - your only job is to \
explain in ONE short sentence (under 220 characters) WHY it beat the \
alternatives, in a natural, direct tone.

Rules you must never break:
- Only use the numbers/times given to you. Never invent, adjust, or round a \
time in a way that changes its meaning, and never invent a reason that \
isn't reflected in the given numbers (e.g. don't claim "crowding" or \
"weather" - you weren't given that data).
- The real reason the winner won is either it arrives sooner, or it's more \
reliable (higher confidence) - name whichever one actually applies by \
comparing the numbers yourself.
- Reflect the given confidence honestly - do not sound more certain than \
the confidence score warrants. Confidence below 0.6 should sound hedged \
("looks like", "should").
- Do not mention "confidence" or "score" as words - translate them into \
natural certainty in your tone instead.
- Output only the sentence, no preamble, no quotes around it."""


def phrase_comparison(winner: RankedRoute, alternatives: list[RankedRoute]) -> str:
    """Like [phrase_recommendation], but for when there were real
    alternatives to weigh - explains WHY the winner beat them (sooner vs.
    more reliable), not just what the winner's own number is. Falls back to
    [phrase_recommendation] (no alternatives to discuss) when the list is
    empty, and to the same template fallback on any LLM failure - same
    fail-soft reasoning as phrase_recommendation's docstring.
    """
    if not alternatives:
        return phrase_recommendation(winner)

    if not settings.anthropic_api_key:
        return _template_comparison_phrase(winner, alternatives)

    client = Anthropic(api_key=settings.anthropic_api_key)

    def _payload(route: RankedRoute) -> dict:
        return {
            "mode": route.mode,
            "label": route.label,
            "predicted_arrival": route.predicted_arrival.isoformat(),
            "confidence": round(route.confidence, 2),
        }

    payload = {
        "winner": _payload(winner),
        "alternatives": [_payload(r) for r in alternatives],
    }

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            system=_COMPARISON_SYSTEM_PROMPT,
            max_tokens=120,
            messages=[{"role": "user", "content": str(payload)}],
        )
        text = _extract_text(response)
        return text if text else _template_comparison_phrase(winner, alternatives)
    except AnthropicError:
        return _template_comparison_phrase(winner, alternatives)


def _template_comparison_phrase(winner: RankedRoute, alternatives: list[RankedRoute]) -> str:
    time_str = winner.predicted_arrival.strftime("%I:%M %p").lstrip("0")
    hedge = "should" if winner.confidence >= 0.6 else "might"
    runner_up = alternatives[0]
    if winner.predicted_arrival < runner_up.predicted_arrival:
        reason = f"sooner than your {runner_up.label}"
    else:
        reason = f"more reliable right now than your {runner_up.label}"
    return f"Your {winner.label} {hedge} arrive around {time_str} - {reason}."


_SCHEDULE_SYSTEM_PROMPT = """You are CommuteOS's Schedule AI - you tell a \
commuter whether to leave now, on schedule, or whether their usual route \
looks disrupted today. You will be given a JSON object with a "severity" \
field ("on_time", "delayed", or "no_live_data"), the usual route's label, \
its live predicted_arrival, and - only for "delayed" - a real \
delay_minutes number. If severity is "no_live_data", you will also be \
given a "substitute" object (mode, label, predicted arrival, confidence) \
- a real alternative a separate scoring system already picked; you are \
not choosing it.

Write ONE short sentence (under 200 characters) telling the commuter what \
to do, in a natural, direct tone:
- "on_time": say their usual route looks on schedule, citing its real \
predicted_arrival time.
- "delayed": say their usual route is running late, citing the REAL \
delay_minutes number given - never invent or round it differently.
- "no_live_data": say their usual route isn't showing live data right \
now and recommend the given substitute instead, citing its real \
predicted_arrival.

Rules you must never break:
- Only use the numbers/times/labels given to you - never invent one.
- Never invent a reason for a delay (weather, crowding, etc.) - you \
weren't given that data.
- Output only the sentence, no preamble, no quotes around it."""


def phrase_schedule_notification(
    assessment: DisruptionAssessment,
    usual_label: str,
    live_predicted_arrival,
    substitute: RankedRoute | None = None,
) -> str:
    """Schedule AI's phrasing entry point - same narrow, fail-soft posture
    as phrase_recommendation/phrase_comparison. [substitute] is required
    when assessment.severity is NO_LIVE_DATA (the real alternative
    decision_engine.rank_routes already picked - this function only
    phrases it, never picks it) and ignored otherwise.
    """
    if not settings.anthropic_api_key:
        return _template_schedule_phrase(assessment, usual_label, live_predicted_arrival, substitute)

    client = Anthropic(api_key=settings.anthropic_api_key)

    payload = {
        "severity": assessment.severity.value,
        "usual_label": usual_label,
        "predicted_arrival": live_predicted_arrival.isoformat() if live_predicted_arrival else None,
        "delay_minutes": round(assessment.delay_minutes, 1) if assessment.delay_minutes is not None else None,
        "substitute": (
            {
                "mode": substitute.mode,
                "label": substitute.label,
                "predicted_arrival": substitute.predicted_arrival.isoformat(),
                "confidence": round(substitute.confidence, 2),
            }
            if substitute is not None
            else None
        ),
    }

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            system=_SCHEDULE_SYSTEM_PROMPT,
            max_tokens=120,
            messages=[{"role": "user", "content": str(payload)}],
        )
        text = _extract_text(response)
        return (
            text
            if text
            else _template_schedule_phrase(assessment, usual_label, live_predicted_arrival, substitute)
        )
    except AnthropicError:
        return _template_schedule_phrase(assessment, usual_label, live_predicted_arrival, substitute)


def _template_schedule_phrase(
    assessment: DisruptionAssessment,
    usual_label: str,
    live_predicted_arrival,
    substitute: RankedRoute | None,
) -> str:
    if assessment.severity == DisruptionSeverity.NO_LIVE_DATA:
        if substitute is None:
            return f"Your usual {usual_label} isn't showing live data right now."
        time_str = substitute.predicted_arrival.strftime("%I:%M %p").lstrip("0")
        return (
            f"Your usual {usual_label} isn't showing live data right now - "
            f"try your {substitute.label}, arriving around {time_str}."
        )

    time_str = live_predicted_arrival.strftime("%I:%M %p").lstrip("0")
    if assessment.severity == DisruptionSeverity.DELAYED:
        delay = round(assessment.delay_minutes or 0)
        return f"Your usual {usual_label} looks about {delay} min later than normal today, arriving around {time_str}."
    return f"Your usual {usual_label} is on schedule, arriving around {time_str}."


_COMMUTE_SYSTEM_PROMPT = """You are CommuteOS's Commute AI - you tell a \
commuter, standing at a station right now, which real option there is \
fastest/most reliable. You will be given a JSON object with a "winner" \
(the recommended option), an "alternatives" list (every other real \
option considered), and a "usual" field - either null (no known usual \
pick for this person here) or a string naming their inferred usual \
choice.

Write ONE short sentence (under 220 characters), natural and direct:
- If "usual" is null, or "usual" equals the winner's own label, just \
recommend the winner and cite its real predicted_arrival time.
- If "usual" is a DIFFERENT label than the winner, explicitly say to \
take the winner INSTEAD of their usual pick, and say why (sooner, or \
more reliable) by comparing the real numbers yourself.

Rules you must never break:
- Only use the numbers/times/labels given to you - never invent one.
- The real reason the winner won is either it arrives sooner, or it's \
more reliable (higher confidence) - name whichever one actually applies.
- Reflect confidence honestly - hedge ("looks like", "should") when \
confidence is below 0.6.
- Do not mention "confidence" or "score" as words.
- Output only the sentence, no preamble, no quotes around it."""


def phrase_commute_recommendation(recommendation: "CommuteRecommendation") -> str:
    """Commute AI's phrasing entry point - same narrow, fail-soft posture
    as every other phrase_* function here. Deliberately takes the whole
    CommuteRecommendation rather than separate args (unlike the schedule/
    comparison functions) since this is the newest caller and there's no
    existing call-site convention to match.
    """
    if not settings.anthropic_api_key:
        return _template_commute_phrase(recommendation)

    client = Anthropic(api_key=settings.anthropic_api_key)

    def _payload(route: RankedRoute) -> dict:
        return {
            "mode": route.mode,
            "label": route.label,
            "predicted_arrival": route.predicted_arrival.isoformat(),
            "confidence": round(route.confidence, 2),
        }

    payload = {
        "winner": _payload(recommendation.winner),
        "alternatives": [_payload(r) for r in recommendation.alternatives],
        "usual": recommendation.usual_route_or_direction,
    }

    try:
        response = client.messages.create(
            model=settings.anthropic_model,
            system=_COMMUTE_SYSTEM_PROMPT,
            max_tokens=120,
            messages=[{"role": "user", "content": str(payload)}],
        )
        text = _extract_text(response)
        return text if text else _template_commute_phrase(recommendation)
    except AnthropicError:
        return _template_commute_phrase(recommendation)


def _template_commute_phrase(recommendation: "CommuteRecommendation") -> str:
    winner = recommendation.winner
    time_str = winner.predicted_arrival.strftime("%I:%M %p").lstrip("0")
    hedge = "should" if winner.confidence >= 0.6 else "might"

    if not recommendation.differs_from_usual:
        return f"Take the {winner.label} - it {hedge} arrive around {time_str}."

    usual_alt = next(
        (a for a in recommendation.alternatives if a.label == recommendation.usual_route_or_direction),
        None,
    )
    if usual_alt is not None and winner.predicted_arrival < usual_alt.predicted_arrival:
        reason = "sooner than your usual"
    else:
        reason = "more reliable right now than your usual"
    return (
        f"Take the {winner.label} instead of your usual {recommendation.usual_route_or_direction} - "
        f"it {hedge} arrive around {time_str}, {reason}."
    )
