import re
import threading
from contextlib import contextmanager
from datetime import datetime


_EVENT_CONTEXT = threading.local()
_STATUS_RE = re.compile(r"\bstatus['\"]?\s*[=:]\s*(\d{3})\b", re.IGNORECASE)
_CODE_RE = re.compile(r"\bcode['\"]?\s*[=:]\s*['\"]?([A-Za-z0-9_:-]+)", re.IGNORECASE)


def _safe_text(value):
    if value is None:
        return ""
    text = str(value)
    return text.replace('"', "'").replace("\n", " ").strip()


def _event_name(event):
    return _safe_text(event).lower().replace(" ", "_")


def _normalize_status(value):
    if value in (None, ""):
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        text = _safe_text(value)
        matched = _STATUS_RE.search(text)
        return matched.group(1) if matched else text


def _normalize_code(value):
    if value in (None, ""):
        return ""
    return _safe_text(value)


def _extract_status(text):
    matched = _STATUS_RE.search(_safe_text(text))
    return matched.group(1) if matched else ""


def _extract_code(text):
    matched = _CODE_RE.search(_safe_text(text))
    return matched.group(1) if matched else ""


def classify_error(exc=None, *, status=None, code=None, message="", detail=""):
    status_value = _normalize_status(status)
    code_value = _normalize_code(code)
    message_value = _safe_text(message)
    detail_value = _safe_text(detail)

    if exc is not None:
        status_value = status_value or _normalize_status(getattr(exc, "status", ""))
        code_value = code_value or _normalize_code(getattr(exc, "code", ""))
        message_value = message_value or _safe_text(getattr(exc, "message", ""))
        detail_value = detail_value or _safe_text(exc)

    status_value = status_value or _extract_status(detail_value) or _extract_status(message_value)
    code_value = code_value or _extract_code(detail_value) or _extract_code(message_value)

    if status_value in {"401", "403"}:
        return "permission_denied"
    if status_value == "404" and code_value == "NotAuthorizedOrNotFound":
        return "permission_denied"
    if status_value == "404":
        return "not_found"
    if status_value == "429":
        return "rate_limited"
    if status_value:
        return "service_error"
    return "unexpected_error"


def _event_kind(level, status, code, message, detail, explicit_kind=None):
    if explicit_kind:
        return _safe_text(explicit_kind)
    normalized_level = _safe_text(level).upper()
    if normalized_level not in {"WARN", "WARNING", "ERROR"}:
        return ""
    if normalized_level in {"WARN", "WARNING"} and not any([status, code, detail]):
        return ""
    return classify_error(status=status, code=code, message=message, detail=detail)


def _event_sink():
    return getattr(_EVENT_CONTEXT, "sink", None)


@contextmanager
def log_event_sink(callback):
    previous = _event_sink()
    _EVENT_CONTEXT.sink = callback
    try:
        yield
    finally:
        _EVENT_CONTEXT.sink = previous


def log_event(
    level,
    service,
    event,
    *,
    region="-",
    compartment="-",
    resource="-",
    message="",
    detail="",
    notify=True,
    **fields,
):
    status = fields.pop("status", "")
    code = fields.pop("code", "")
    explicit_kind = fields.pop("kind", "")
    status_value = _normalize_status(status) or _extract_status(detail) or _extract_status(message)
    code_value = _normalize_code(code) or _extract_code(detail) or _extract_code(message)
    kind = _event_kind(level, status_value, code_value, message, detail, explicit_kind)
    normalized_level = _safe_text(level).upper()
    if kind == "permission_denied" and normalized_level == "ERROR":
        normalized_level = "WARN"

    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": normalized_level,
        "service": _safe_text(service),
        "region": _safe_text(region) or "-",
        "compartment": _safe_text(compartment) or "-",
        "resource": _safe_text(resource) or "-",
        "event": _event_name(event),
        "kind": kind,
        "status": status_value,
        "code": code_value,
        "message": _safe_text(message),
        "detail": _safe_text(detail),
    }
    for key, value in fields.items():
        if value is None:
            continue
        payload[_safe_text(key)] = value

    parts = [
        f"ts={ts}",
        f"service={payload['service']}",
        f"event={payload['event']}",
        f"region={payload['region']}",
        f"compartment={payload['compartment']}",
        f"resource={payload['resource']}",
    ]

    if payload["kind"]:
        parts.append(f"kind={payload['kind']}")
    if payload["status"]:
        parts.append(f"status={payload['status']}")
    if payload["code"]:
        parts.append(f"code={payload['code']}")
    if payload["message"]:
        parts.append(f'message="{payload["message"]}"')
    if payload["detail"]:
        parts.append(f'detail="{payload["detail"]}"')

    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{_safe_text(key)}={_safe_text(value)}")

    print(f"[{normalized_level}] " + " ".join(parts))

    sink = _event_sink()
    if notify and sink:
        sink(dict(payload))
    return payload
