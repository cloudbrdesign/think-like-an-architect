"""The learner-facing API client: POST /ask with a bearer token, exactly as any caller would."""
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class Response:
    status: int
    body: object          # parsed JSON, or the raw text
    headers: dict
    raw: str
    retries: int = 0

    @property
    def request_id(self):
        return self.body.get("request_id") if isinstance(self.body, dict) else None


def ask(endpoint, token, question, extra_body=None, headers=None, query=""):
    payload = {"question": question, **(extra_body or {})}
    request = urllib.request.Request(f"{endpoint.rstrip('/')}/ask{('?' + query) if query else ''}",
                                     data=json.dumps(payload).encode(), method="POST",
                                     headers={"content-type": "application/json", **(headers or {}),
                                              **({"authorization": f"Bearer {token}"} if token else {})})
    retries = 0
    while True:
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw, status, response_headers = response.read().decode(), response.status, dict(response.headers)
            break
        except urllib.error.HTTPError as error:               # any HTTP status is an observation, never retried
            raw, status, response_headers = error.read().decode(), error.code, dict(error.headers)
            break
        except (TimeoutError, urllib.error.URLError) as error:  # the client never got an answer: retry once, recorded
            if retries >= 1:
                raise
            retries += 1
            time.sleep(5)
    try:
        body = json.loads(raw)
    except ValueError:
        body = raw
    return Response(status, body, {k.lower(): v for k, v in response_headers.items()}, raw, retries)
