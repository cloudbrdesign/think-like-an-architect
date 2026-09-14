"""API calls as an end user. Captures status, body, the x-tla-event-id header and the edge request ID."""
import json
import time
import urllib.error
import urllib.request


class Response:
    def __init__(self, status, body, headers):
        self.status = status
        self.body = body
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.event_id = self.headers.get("x-tla-event-id")
        self.request_id = self.headers.get("apigw-requestid")

    def code(self):
        return (self.body or {}).get("error", {}).get("code") if isinstance(self.body, dict) else None

    def summary(self):
        return {"status": self.status, "code": self.code(), "event_id": self.event_id, "request_id": self.request_id}


class Api:
    def __init__(self, endpoint):
        self.endpoint = endpoint.rstrip("/")

    def call(self, method, path, token=None, body=None, headers=None, authorization=None, query=""):
        url = self.endpoint + path + (("?" + query) if query else "")
        request_headers = {"content-type": "application/json"}
        if token is not None:
            request_headers["authorization"] = f"Bearer {token}"
        if authorization is not None:
            request_headers["authorization"] = authorization
        request_headers.update(headers or {})
        data = json.dumps(body).encode("utf-8") if body is not None else None
        for attempt in range(4):
            request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
            try:
                with urllib.request.urlopen(request, timeout=40) as reply:
                    status, raw, reply_headers = reply.status, reply.read(), dict(reply.headers)
            except urllib.error.HTTPError as error:
                status, raw, reply_headers = error.code, error.read(), dict(error.headers)
            # Retry only edge throttling; every application answer, including refusals, is returned as observed.
            if status == 429 and attempt < 3:
                time.sleep(2 * (attempt + 1))
                continue
            break
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            parsed = raw.decode("utf-8", errors="replace")
        return Response(status, parsed, reply_headers)
