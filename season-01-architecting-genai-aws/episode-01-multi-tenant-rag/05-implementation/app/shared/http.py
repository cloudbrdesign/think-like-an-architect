"""HTTP API (payload 2.0) responses. Every response carries x-tla-event-id, the key of its audit record."""
import json

from shared.reason_codes import MESSAGES


def response(status, body, event_id):
    return {"statusCode": status,
            "headers": {"content-type": "application/json", "cache-control": "no-store", "x-tla-event-id": event_id},
            "body": json.dumps(body)}


def refusal(reason, event_id):
    return response(reason.status, {"error": {"code": reason.code, "message": MESSAGES.get(reason.code, "Refused.")},
                                    "event_id": event_id}, event_id)
