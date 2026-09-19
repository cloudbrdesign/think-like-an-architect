"""Identity and trusted request context (CTL-002; boundary B1 → B2).

The HTTP API's JWT authorizer has already verified the access token's signature, issuer, client and expiry before this
function runs; an invalid token never reaches it. From the verified claims this module takes ONE value: `sub`, the
identity subject that keys the authoritative grants store.

Everything else a client can influence — body fields other than `question`, query strings, headers, the question text,
extra token claims such as `cognito:groups` — is NOT an authorization input. The verified claims are carried along
unchanged so that a learner can see they are available and deliberately not used (experiment 3 shows what happens when
they are).
"""
import json
import re
from dataclasses import dataclass, field

from core.reason_codes import REFUSED_AUTHORIZATION_UNAVAILABLE, REFUSED_INVALID_REQUEST, Refusal

SUBJECT = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
MAX_QUESTION_CHARACTERS = 1000


@dataclass(frozen=True)
class TrustedContext:
    requester_sub: str
    verified_claims: dict = field(default_factory=dict, compare=False, repr=False)


def resolve(event):
    claims = (((event or {}).get("requestContext") or {}).get("authorizer") or {}).get("jwt", {}).get("claims") or {}
    subject = claims.get("sub")
    if not isinstance(subject, str) or not SUBJECT.match(subject) or claims.get("token_use") != "access":
        raise Refusal(REFUSED_AUTHORIZATION_UNAVAILABLE, "no verified subject")
    return TrustedContext(subject, dict(claims))


def question(event):
    """The question is read from the JSON body field `question` and used only as the search and generation text."""
    try:
        body = json.loads((event or {}).get("body") or "{}")
    except (TypeError, ValueError) as error:
        raise Refusal(REFUSED_INVALID_REQUEST, "body is not JSON") from error
    text = body.get("question") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_QUESTION_CHARACTERS:
        raise Refusal(REFUSED_INVALID_REQUEST, "question missing or too long")
    return text.strip()
