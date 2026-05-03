from datetime import datetime


def _safe_text(value):
    if value is None:
        return ""
    text = str(value)
    return text.replace('"', "'").replace("\n", " ").strip()


def _event_name(event):
    return _safe_text(event).lower().replace(" ", "_")


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
    **fields,
):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    parts = [
        f"ts={ts}",
        f"service={_safe_text(service)}",
        f"event={_event_name(event)}",
        f"region={_safe_text(region) or '-'}",
        f"compartment={_safe_text(compartment) or '-'}",
        f"resource={_safe_text(resource) or '-'}",
    ]

    if message:
        parts.append(f'message="{_safe_text(message)}"')
    if detail:
        parts.append(f'detail="{_safe_text(detail)}"')

    for key, value in fields.items():
        if value is None:
            continue
        parts.append(f"{_safe_text(key)}={_safe_text(value)}")

    print(f"[{_safe_text(level).upper()}] " + " ".join(parts))
