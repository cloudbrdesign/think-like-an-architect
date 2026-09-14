"""Minimal DynamoDB attribute-value codec (standard library only, so component tests run without the AWS SDK)."""
from decimal import Decimal


def to_attr(value):
    if value is None:
        return {"NULL": True}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, (int, Decimal)):
        return {"N": str(value)}
    if isinstance(value, float):
        return {"N": repr(value)}
    if isinstance(value, (list, tuple)):
        return {"L": [to_attr(v) for v in value]}
    if isinstance(value, dict):
        return {"M": {k: to_attr(v) for k, v in value.items()}}
    raise TypeError(f"unsupported attribute type: {type(value).__name__}")


def from_attr(attr):
    (kind, value), = attr.items()
    if kind == "NULL":
        return None
    if kind in ("S", "BOOL"):
        return value
    if kind == "N":
        return int(value) if value.lstrip("-").isdigit() else float(value)
    if kind == "L":
        return [from_attr(v) for v in value]
    if kind == "M":
        return {k: from_attr(v) for k, v in value.items()}
    raise TypeError(f"unsupported attribute kind: {kind}")


def to_item(record):
    return {k: to_attr(v) for k, v in record.items()}


def from_item(item):
    return {k: from_attr(v) for k, v in item.items()}
