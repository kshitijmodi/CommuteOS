"""NJ Transit real-time fetching - SCAFFOLD ONLY, not yet implemented.

Deliberately not wired up to a real endpoint yet: as of this writing the
user's NJ Transit developer account is still pending manual approval (see
OPEN_QUESTIONS.md), so there are no credentials to test against, and
research into NJ Transit's API turned up real uncertainty worth flagging
rather than guessing past:

- Auth is username+password (possibly a token exchange layered on top),
  not a simple API key like MTA/PATH - see NjtCredentials below.
- The rail real-time interface is a legacy SOAP/XML web service
  (NJTTrainData.asmx), NOT GTFS-realtime protobuf like MTA. NJ Transit's
  terms also mention a GTFS-RT option exists, but the actual endpoint URL
  for it is gated behind login and unconfirmed.
- The bus API's wire format (JSON/XML/SOAP) is unconfirmed from public
  sources.
- Rate limits are real and asymmetric: reportedly ~10 requests/day for
  full schedule pulls vs. 40,000/day for live vehicle data - schedule
  data must be cached aggressively once this is implemented, not polled.

get_arrivals() intentionally raises NotImplementedError rather than
guessing a response shape - once real credentials arrive, inspect an
actual response before writing the parser, the same way MTA/PATH were
each verified against live data before their parsers were written.
"""

from dataclasses import dataclass

from .models import ArrivalsResult


@dataclass(frozen=True)
class NjtCredentials:
    username: str
    password: str


async def get_arrivals(station_code: str, credentials: NjtCredentials) -> ArrivalsResult:
    raise NotImplementedError(
        "NJ Transit integration is scaffolded but not implemented - "
        "waiting on developer account approval to confirm the real "
        "request/response shape. See app/transit/njt.py's module "
        "docstring and OPEN_QUESTIONS.md."
    )
