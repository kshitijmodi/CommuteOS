"""Phase 3 LLM phrasing layer. Per the PRD, the LLM's job is narrow and
specific: take the decision engine's structured output and phrase it as a
sentence - it never sees raw trip history, never picks the route itself,
and is never asked to invent a number that isn't already in the input.
This is the highest-risk-of-hallucination surface in the whole system
(inventing a departure time has a real consequence - a missed train), so
the prompt is deliberately narrow and the temperature is low.

Uses an OpenAI-compatible client pointed at Groq (the user's available API
key) rather than OpenAI/Gemini directly as the PRD's tech stack lists -
Groq's API is OpenAI-compatible, so this is a one-line base_url swap away
from either of those if needed later.

Fails soft, not hard: if no API key is configured or the call errors, this
falls back to a deterministic template (see _template_phrase) instead of
raising - a recommendation with slightly worse prose beats no
recommendation at all, and this is explicitly a "nice to have" layer per
the PRD (phrasing only, never the decision).
"""

from openai import OpenAI, OpenAIError

from .core.config import settings
from .decision_engine import RankedRoute

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
    if not settings.groq_api_key:
        return _template_phrase(route)

    client = OpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    payload = {
        "mode": route.mode,
        "label": route.label,
        "predicted_arrival": route.predicted_arrival.isoformat(),
        "confidence": round(route.confidence, 2),
    }

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            max_tokens=100,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": str(payload)},
            ],
        )
        text = response.choices[0].message.content
        return text.strip() if text else _template_phrase(route)
    except OpenAIError:
        return _template_phrase(route)


def _template_phrase(route: RankedRoute) -> str:
    time_str = route.predicted_arrival.strftime("%I:%M %p").lstrip("0")
    hedge = "should" if route.confidence >= 0.6 else "might"
    return f"Your {route.label} {hedge} arrive around {time_str}."
