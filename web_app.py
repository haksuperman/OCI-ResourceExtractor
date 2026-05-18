import os
import threading
import time
import uuid
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import parse_qs

import common
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from runner import SERVICE_REGISTRY, run_inventory


app = FastAPI(title="OCI Resource Extractor")

JOB_LOCK = threading.Lock()
STORE_LOCK = threading.Lock()
JOBS = {}
MAX_EVENTS_PER_JOB = 500

SERVICE_LABELS = {
    "compute": "Compute Instance",
    "instance_pools": "Instance Pools / Autoscaling",
    "vcn": "VCN",
    "vpn": "VPN",
    "fastconnect": "FastConnect",
    "dns": "DNS",
    "load_balancer": "Load Balancer",
    "network_load_balancer": "Network Load Balancer",
    "block_storage": "Block Storage",
    "file_storage": "File Storage",
    "object_storage": "Object Storage",
    "dbcs": "Base Database",
    "adb": "Autonomous Database",
    "mysql": "MySQL HeatWave",
    "waf": "WAF",
    "waf_edge": "WAF Edge",
}

SERVICE_GROUPS = [
    ("Compute", ["compute", "instance_pools"]),
    (
        "Networking",
        [
            "vcn",
            "vpn",
            "fastconnect",
            "dns",
            "load_balancer",
            "network_load_balancer",
        ],
    ),
    ("Storage", ["block_storage", "file_storage", "object_storage"]),
    ("Databases", ["dbcs", "adb", "mysql"]),
    ("Identity & Security", ["waf", "waf_edge"]),
]

BASE_CSS = """
:root {
  --bg: #f4f6f8;
  --surface: #ffffff;
  --surface-soft: #f8fafc;
  --line: #d7dde5;
  --line-strong: #b8c2cf;
  --text: #17202e;
  --muted: #667085;
  --muted-strong: #475467;
  --accent: #0f766e;
  --accent-dark: #115e59;
  --accent-soft: #e6f4f1;
  --warn: #9a5b00;
  --warn-soft: #fff7df;
  --permission: #7c3d00;
  --permission-soft: #fff4e5;
  --error: #b42318;
  --error-soft: #fff1f0;
  --ok: #0f7a45;
  --ok-soft: #ecfdf3;
  --info: #1d5fbf;
  --info-soft: #edf4ff;
  --shadow: 0 10px 30px rgba(16, 24, 40, 0.06);
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 14px;
  line-height: 1.5;
}
button,
input,
select {
  font: inherit;
}
a {
  color: var(--accent-dark);
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
.app-header {
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.header-inner {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin: 0 auto;
  max-width: 1240px;
  min-height: 72px;
  padding: 16px 28px;
}
.brand h1 {
  font-size: 21px;
  font-weight: 750;
  letter-spacing: 0;
  line-height: 1.2;
  margin: 0;
}
.brand p {
  color: var(--muted);
  margin: 5px 0 0;
}
.header-meta {
  color: var(--muted-strong);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
main {
  margin: 0 auto;
  max-width: 1240px;
  padding: 24px 28px 36px;
}
.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.75fr);
  gap: 18px;
}
.stack {
  display: grid;
  gap: 18px;
}
.panel {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow);
}
.panel-header {
  align-items: flex-start;
  border-bottom: 1px solid var(--line);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 16px 18px;
}
.panel-header h2 {
  font-size: 16px;
  font-weight: 750;
  line-height: 1.25;
  margin: 0;
}
.panel-header p {
  color: var(--muted);
  margin: 4px 0 0;
}
.panel-body {
  padding: 18px;
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}
.field-wide {
  grid-column: span 2;
}
.field label,
.service-tools label {
  color: var(--muted-strong);
  display: block;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 6px;
}
input[type="text"],
select {
  background: var(--surface);
  border: 1px solid #c7cfda;
  border-radius: 6px;
  color: var(--text);
  height: 40px;
  padding: 8px 10px;
  width: 100%;
}
input[type="text"]:focus,
select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  outline: none;
}
.hint {
  color: var(--muted);
  font-size: 12px;
  margin: 6px 0 0;
}
.section-divider {
  border-top: 1px solid var(--line);
  margin: 18px 0;
}
.service-toolbar {
  align-items: end;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: 12px;
  margin-bottom: 14px;
}
.scope-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}
.scope-block {
  border: 1px solid var(--line);
  border-radius: 8px;
  min-width: 0;
  overflow: hidden;
}
.scope-block-header,
.log-toolbar,
.progress-meta {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
}
.scope-block-header {
  background: #f1f4f8;
  border-bottom: 1px solid var(--line);
  padding: 10px 12px;
}
.scope-block-title {
  font-size: 13px;
  font-weight: 800;
}
.scope-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.scope-list {
  display: grid;
  gap: 6px;
  max-height: 220px;
  overflow: auto;
  padding: 10px;
}
.scope-option {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: 16px minmax(0, 1fr);
  margin: 0;
}
.scope-option input {
  height: 15px;
  margin: 0;
  width: 15px;
}
.scope-option span {
  overflow-wrap: anywhere;
}
.scope-status {
  color: var(--muted);
  padding: 12px;
}
.manual-row {
  border-top: 1px solid var(--line);
  padding: 10px;
}
.button-group {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.service-group {
  margin-top: 16px;
}
.service-group:first-of-type {
  margin-top: 0;
}
.service-group-title {
  align-items: center;
  color: var(--muted-strong);
  display: flex;
  font-size: 12px;
  font-weight: 800;
  justify-content: space-between;
  margin-bottom: 8px;
  text-transform: uppercase;
}
.service-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}
.service-option {
  align-items: center;
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 8px;
  cursor: pointer;
  display: grid;
  gap: 10px;
  grid-template-columns: 18px minmax(0, 1fr) auto;
  margin: 0;
  min-height: 54px;
  padding: 10px;
}
.service-option:hover {
  border-color: var(--line-strong);
}
.service-option input {
  height: 16px;
  margin: 0;
  width: 16px;
}
.service-name {
  display: block;
  font-weight: 750;
  overflow-wrap: anywhere;
}
.service-key {
  color: var(--muted);
  display: block;
  font-size: 12px;
  margin-top: 1px;
  overflow-wrap: anywhere;
}
.scope-badge,
.status-badge,
.level-badge,
.health-badge,
.count-badge,
.chip {
  align-items: center;
  border-radius: 999px;
  display: inline-flex;
  font-size: 12px;
  font-weight: 750;
  line-height: 1;
  min-height: 24px;
  padding: 5px 8px;
  white-space: nowrap;
}
.scope-badge {
  background: #eef2f6;
  color: var(--muted-strong);
}
.count-badge {
  background: var(--accent-soft);
  color: var(--accent-dark);
}
.status-badge.status-completed,
.health-badge.health-ok,
.level-badge.level-info {
  background: var(--ok-soft);
  color: var(--ok);
}
.status-badge.status-running,
.status-badge.status-queued {
  background: var(--info-soft);
  color: var(--info);
}
.status-badge.status-failed,
.health-badge.health-failed,
.level-badge.level-error {
  background: var(--error-soft);
  color: var(--error);
}
.health-badge.health-partial,
.level-badge.level-warn,
.level-badge.level-warning {
  background: var(--warn-soft);
  color: var(--warn);
}
.health-badge.health-permission-limited {
  background: var(--permission-soft);
  color: var(--permission);
}
.health-badge.health-no-data {
  background: #eef2f6;
  color: var(--muted-strong);
}
.status-badge.status-unknown,
.level-badge.level-other,
.health-badge.health-unknown {
  background: #eef2f6;
  color: var(--muted-strong);
}
.actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}
button,
.button {
  align-items: center;
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 6px;
  color: #ffffff;
  cursor: pointer;
  display: inline-flex;
  font-weight: 750;
  gap: 8px;
  justify-content: center;
  min-height: 40px;
  padding: 8px 14px;
  text-decoration: none;
}
button:hover,
.button:hover {
  background: var(--accent-dark);
  border-color: var(--accent-dark);
  text-decoration: none;
}
button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.button.secondary,
button.secondary {
  background: var(--surface);
  color: var(--accent-dark);
}
.button.secondary:hover,
button.secondary:hover {
  background: var(--accent-soft);
}
.button.subtle,
button.subtle {
  background: #f2f4f7;
  border-color: #d0d5dd;
  color: var(--muted-strong);
}
.button.subtle:hover,
button.subtle:hover {
  background: #e9edf3;
}
.button-icon {
  display: inline-flex;
  height: 16px;
  width: 16px;
}
.button-icon svg {
  display: block;
  height: 16px;
  width: 16px;
}
.notice {
  background: var(--error-soft);
  border: 1px solid #f3b9b3;
  border-radius: 8px;
  color: var(--error);
  margin-bottom: 18px;
  padding: 12px 14px;
  white-space: pre-wrap;
}
.table-wrap {
  overflow-x: auto;
}
.log-toolbar {
  border-bottom: 1px solid var(--line);
  padding: 12px 18px;
}
.segmented {
  background: #eef2f6;
  border: 1px solid var(--line);
  border-radius: 8px;
  display: inline-flex;
  gap: 2px;
  padding: 2px;
}
.segmented button {
  background: transparent;
  border-color: transparent;
  color: var(--muted-strong);
  min-height: 32px;
  padding: 6px 10px;
}
.segmented button.active {
  background: var(--surface);
  border-color: var(--line);
  color: var(--text);
}
.log-search {
  min-width: min(320px, 100%);
}
table {
  border-collapse: collapse;
  font-size: 13px;
  width: 100%;
}
th,
td {
  border-bottom: 1px solid var(--line);
  padding: 10px 9px;
  text-align: left;
  vertical-align: top;
}
th {
  background: #f1f4f8;
  color: var(--muted-strong);
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
td {
  overflow-wrap: anywhere;
}
tbody tr:hover td {
  background: #fbfcfe;
}
.empty-cell {
  color: var(--muted);
  text-align: center;
}
.job-link {
  font-weight: 750;
}
.status-panel {
  display: grid;
  gap: 16px;
}
.status-topline {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: space-between;
}
.progress-track {
  background: #e7ecf2;
  border-radius: 999px;
  height: 10px;
  overflow: hidden;
}
.progress-bar {
  background: var(--accent);
  border-radius: inherit;
  height: 100%;
  transition: width 0.25s ease;
  width: 0;
}
.progress-bar.is-active {
  background: linear-gradient(90deg, var(--accent), #1d8f82, var(--accent));
  background-size: 180% 100%;
  animation: pulsebar 1.4s ease-in-out infinite;
}
.progress-meta {
  color: var(--muted-strong);
  font-size: 12px;
  font-weight: 750;
}
.progress-meta strong {
  color: var(--text);
}
@keyframes pulsebar {
  0% { background-position: 0 0; }
  100% { background-position: 180% 0; }
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--line);
}
.metric {
  background: var(--surface);
  min-height: 72px;
  padding: 12px;
}
.metric span {
  color: var(--muted);
  display: block;
  font-size: 12px;
  font-weight: 700;
}
.metric strong {
  display: block;
  font-size: 15px;
  margin-top: 5px;
  overflow-wrap: anywhere;
}
.summary-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 10px;
}
.summary-item {
  background: var(--surface-soft);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 11px 12px;
}
.summary-item span {
  color: var(--muted);
  display: block;
  font-size: 12px;
  font-weight: 700;
}
.summary-item strong {
  display: block;
  font-size: 18px;
  margin-top: 2px;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  background: #eef2f6;
  color: var(--muted-strong);
}
.error-box {
  background: var(--error-soft);
  border: 1px solid #f3b9b3;
  border-radius: 8px;
  color: var(--error);
  padding: 12px;
  white-space: pre-wrap;
}
[hidden] {
  display: none !important;
}
@media (max-width: 980px) {
  .workspace-grid,
  .field-grid,
  .scope-grid,
  .summary-strip,
  .metric-grid {
    grid-template-columns: 1fr;
  }
  .field-wide {
    grid-column: auto;
  }
  .header-inner {
    align-items: flex-start;
    flex-direction: column;
  }
  .header-meta {
    justify-content: flex-start;
  }
}
@media (max-width: 720px) {
  main {
    padding: 16px;
  }
  .header-inner {
    padding: 16px;
  }
  .panel-header,
  .status-topline,
  .service-toolbar,
  .scope-block-header,
  .log-toolbar,
  .actions {
    align-items: stretch;
    flex-direction: column;
  }
  .service-toolbar,
  .service-grid {
    grid-template-columns: 1fr;
  }
  .button-group {
    justify-content: stretch;
  }
  button,
  .button {
    width: 100%;
  }
}
"""


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _duration_text(start_ts, end_ts=None):
    if not start_ts:
        return "-"
    end = end_ts or time.time()
    seconds = int(end - start_ts)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _csv_text(value):
    if not value:
        return "-"
    if isinstance(value, str):
        return value or "-"
    return ", ".join(value) if value else "-"


def _safe(value):
    return escape(str(value)) if value is not None else ""


def _normalize_filter_values(values):
    if not values:
        return []
    if isinstance(values, str):
        return [item.strip() for item in values.split(",") if item.strip()]
    return [str(item).strip() for item in values if str(item).strip()]


def _service_label(service_name):
    return SERVICE_LABELS.get(service_name, service_name.replace("_", " ").title())


def _service_scope(service_name):
    for service in SERVICE_REGISTRY:
        if service["name"] == service_name:
            return service["scope"]
    return "-"


def _status_class(status):
    normalized = str(status or "unknown").lower()
    if normalized in {"queued", "running", "completed", "failed"}:
        return f"status-{normalized}"
    return "status-unknown"


def _level_class(level):
    normalized = str(level or "other").lower()
    if normalized in {"info", "warn", "warning", "error"}:
        return f"level-{normalized}"
    return "level-other"


def _status_badge(status):
    return (
        f'<span class="status-badge {_safe(_status_class(status))}">'
        f"{_safe(status or 'unknown')}</span>"
    )


def _level_badge(level):
    return (
        f'<span class="level-badge {_safe(_level_class(level))}">'
        f"{_safe(level or '-')}</span>"
    )


def _icon(name):
    icons = {
        "play": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<polygon points="6 3 20 12 6 21 6 3"></polygon></svg>'
        ),
        "refresh": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74"></path>'
            '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74"></path>'
            '<path d="M8 18H3v5"></path><path d="M16 6h5V1"></path></svg>'
        ),
        "download": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>'
            '<path d="M7 10l5 5 5-5"></path><path d="M12 15V3"></path></svg>'
        ),
        "back": (
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M19 12H5"></path><path d="M12 19l-7-7 7-7"></path></svg>'
        ),
    }
    svg = icons.get(name, "")
    return f'<span class="button-icon" aria-hidden="true">{svg}</span>' if svg else ""


def _event_summary(events):
    summary = {
        "events": len(events),
        "warnings": 0,
        "permission_denied": 0,
        "errors": 0,
        "collected": 0,
    }
    for event in events:
        level = str(event.get("level", "")).upper()
        if level == "WARN" or level == "WARNING":
            summary["warnings"] += 1
        elif level == "ERROR":
            summary["errors"] += 1
        if event.get("kind") == "permission_denied":
            summary["permission_denied"] += 1

        if event.get("event") == "step_end":
            try:
                summary["collected"] += int(event.get("collected") or 0)
            except (TypeError, ValueError):
                pass
    return summary


def _progress_details(job):
    completed_steps = int(job.get("completed_steps") or 0)
    total_steps = job.get("total_steps")
    try:
        total_steps = int(total_steps) if total_steps is not None else None
    except (TypeError, ValueError):
        total_steps = None

    if total_steps and total_steps > 0:
        percent = min(100, int((completed_steps / total_steps) * 100))
        if job.get("status") == "completed":
            percent = 100
        return {
            "total_steps": total_steps,
            "progress_percent": percent,
            "progress_label": f"{completed_steps} / {total_steps}",
        }

    percent = 100 if job.get("status") == "completed" else 0
    return {
        "total_steps": total_steps,
        "progress_percent": percent,
        "progress_label": str(completed_steps),
    }


def _job_snapshot(job_id):
    with STORE_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return None
        snapshot = dict(job)
        snapshot["events"] = list(job.get("events", []))
        snapshot["service_results"] = list(job.get("service_results", []))
    return snapshot


def _append_job_event(job_id, payload):
    with STORE_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        events = job.setdefault("events", [])
        events.append(payload)
        if len(events) > MAX_EVENTS_PER_JOB:
            del events[: len(events) - MAX_EVENTS_PER_JOB]
        job["updated_at"] = _now()

        event = payload.get("event")
        if payload.get("total_steps") is not None:
            try:
                job["total_steps"] = int(payload.get("total_steps"))
            except (TypeError, ValueError):
                job["total_steps"] = payload.get("total_steps")

        if event == "step_start":
            job["current_step"] = (
                f"{payload.get('step_service', '-')}"
                f" / {payload.get('step_region', '-')}"
            )
        elif event == "step_end":
            job["completed_steps"] = int(job.get("completed_steps", 0)) + 1
        elif event == "run_end":
            job["current_step"] = "report generated"


def _run_job(job_id, profile, regions, compartments, service_names):
    with STORE_LOCK:
        job = JOBS[job_id]
        job["status"] = "running"
        job["started_at"] = _now()
        job["started_ts"] = time.time()
        job["current_step"] = "initializing"

    try:
        result = run_inventory(
            profile,
            regions=regions,
            compartments=compartments,
            service_names=service_names,
            progress_callback=lambda payload: _append_job_event(job_id, payload),
        )
        with STORE_LOCK:
            job = JOBS[job_id]
            job["status"] = "completed"
            job["finished_at"] = _now()
            job["finished_ts"] = time.time()
            job["report_path"] = result.get("report_path")
            job["json_paths"] = result.get("json_paths", {})
            job["service_results"] = result.get("service_results", [])
            job["run_summary"] = result.get("run_summary", {})
            job["diagnostics"] = result.get("diagnostics", [])
            job["total_steps"] = result.get("total_steps", job.get("total_steps"))
            job["current_step"] = "completed"
    except Exception as exc:
        with STORE_LOCK:
            job = JOBS[job_id]
            job["status"] = "failed"
            job["finished_at"] = _now()
            job["finished_ts"] = time.time()
            job["error"] = str(exc)
            job["current_step"] = "failed"
            job.setdefault("events", []).append(
                {
                    "timestamp": _now(),
                    "level": "ERROR",
                    "service": "web",
                    "event": "job_failed",
                    "message": str(exc),
                }
            )
    finally:
        JOB_LOCK.release()


def _home_script():
    return """
<script>
(() => {
  const serviceCards = Array.from(document.querySelectorAll("[data-service-option]"));
  const serviceChecks = Array.from(document.querySelectorAll("[data-service-checkbox]"));
  const selectedCount = document.querySelector("[data-selected-count]");
  const filterInput = document.querySelector("[data-service-filter]");
  const selectAll = document.querySelector("[data-select-all]");
  const clearServices = document.querySelector("[data-clear-services]");
  const profileSelect = document.querySelector("#profile");
  const runForm = document.querySelector("[data-run-form]");
  const scopeStatus = document.querySelector("[data-scope-status]");
  const scopeKinds = ["regions", "compartments"];
  const scopeState = {
    regions: { loaded: false, values: [] },
    compartments: { loaded: false, values: [] }
  };

  function cell(value) {
    return String(value === null || value === undefined || value === "" ? "-" : value);
  }

  function esc(value) {
    return cell(value).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    }[ch]));
  }

  function refreshCount() {
    if (!selectedCount) return;
    const count = serviceChecks.filter((item) => item.checked).length;
    selectedCount.textContent = `${count} selected`;
  }

  function applyFilter() {
    const query = (filterInput && filterInput.value || "").trim().toLowerCase();
    serviceCards.forEach((card) => {
      const name = (card.dataset.serviceName || "").toLowerCase();
      const label = (card.dataset.serviceLabel || "").toLowerCase();
      card.hidden = Boolean(query) && !name.includes(query) && !label.includes(query);
    });
  }

  function scopeLabel(kind, item) {
    return kind === "regions" ? item : item.name;
  }

  function scopeValue(kind, item) {
    return kind === "regions" ? item : item.name;
  }

  function refreshScope(kind) {
    const hidden = document.querySelector(`[data-scope-hidden="${kind}"]`);
    const manual = document.querySelector(`[data-scope-manual="${kind}"]`);
    const count = document.querySelector(`[data-scope-count="${kind}"]`);
    const checks = Array.from(document.querySelectorAll(`[data-scope-checkbox="${kind}"]`));
    const manualValue = manual ? manual.value.trim() : "";

    if (manualValue) {
      if (hidden) hidden.value = manualValue;
      if (count) count.textContent = "manual";
      return;
    }

    const selected = checks.filter((item) => item.checked).map((item) => item.value);
    if (hidden) {
      hidden.value = selected.length === checks.length ? "" : selected.join(",");
    }
    if (count) {
      count.textContent = checks.length
        ? `${selected.length} / ${checks.length}`
        : "-";
    }
  }

  function renderScope(kind, items) {
    const list = document.querySelector(`[data-scope-list="${kind}"]`);
    if (!list) return;
    scopeState[kind] = { loaded: true, values: items };
    list.innerHTML = "";

    if (!items.length) {
      list.innerHTML = `<div class="scope-status">조회된 항목이 없습니다.</div>`;
      refreshScope(kind);
      return;
    }

    items.forEach((item) => {
      const value = scopeValue(kind, item);
      const label = scopeLabel(kind, item);
      const option = document.createElement("label");
      option.className = "scope-option";
      option.innerHTML = `
        <input data-scope-checkbox="${kind}" type="checkbox" value="${esc(value)}" checked>
        <span>${esc(label)}</span>
      `;
      list.appendChild(option);
    });

    Array.from(document.querySelectorAll(`[data-scope-checkbox="${kind}"]`)).forEach((item) => {
      item.addEventListener("change", () => refreshScope(kind));
    });
    refreshScope(kind);
  }

  function setScopeLoading(message) {
    if (scopeStatus) scopeStatus.textContent = message;
    scopeKinds.forEach((kind) => {
      const list = document.querySelector(`[data-scope-list="${kind}"]`);
      if (list) list.innerHTML = `<div class="scope-status">${esc(message)}</div>`;
      const count = document.querySelector(`[data-scope-count="${kind}"]`);
      if (count) count.textContent = "-";
    });
  }

  async function loadScope() {
    if (!profileSelect || profileSelect.disabled || !profileSelect.value) return;
    scopeKinds.forEach((kind) => {
      const manual = document.querySelector(`[data-scope-manual="${kind}"]`);
      if (manual) manual.value = "";
      const hidden = document.querySelector(`[data-scope-hidden="${kind}"]`);
      if (hidden) hidden.value = "";
    });
    setScopeLoading("Profile scope 조회 중...");
    try {
      const response = await fetch(`/api/profiles/${encodeURIComponent(profileSelect.value)}/scope`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || payload.error || "scope lookup failed");
      }
      if (scopeStatus) {
        scopeStatus.textContent = `${payload.tenancy_name} / ${payload.regions.length} regions / ${payload.compartments.length} compartments`;
      }
      renderScope("regions", payload.regions || []);
      renderScope("compartments", payload.compartments || []);
    } catch (error) {
      setScopeLoading(`Scope 조회 실패: ${error.message}`);
      scopeKinds.forEach((kind) => {
        scopeState[kind] = { loaded: false, values: [] };
        refreshScope(kind);
      });
    }
  }

  function setScopeChecks(kind, checked) {
    Array.from(document.querySelectorAll(`[data-scope-checkbox="${kind}"]`)).forEach((item) => {
      item.checked = checked;
    });
    refreshScope(kind);
  }

  serviceChecks.forEach((item) => item.addEventListener("change", refreshCount));
  if (filterInput) filterInput.addEventListener("input", applyFilter);
  if (selectAll) {
    selectAll.addEventListener("click", () => {
      serviceChecks.forEach((item) => { item.checked = true; });
      refreshCount();
    });
  }
  if (clearServices) {
    clearServices.addEventListener("click", () => {
      serviceChecks.forEach((item) => { item.checked = false; });
      refreshCount();
    });
  }
  scopeKinds.forEach((kind) => {
    const manual = document.querySelector(`[data-scope-manual="${kind}"]`);
    if (manual) manual.addEventListener("input", () => refreshScope(kind));
    const all = document.querySelector(`[data-scope-select-all="${kind}"]`);
    if (all) all.addEventListener("click", () => setScopeChecks(kind, true));
    const clear = document.querySelector(`[data-scope-clear="${kind}"]`);
    if (clear) clear.addEventListener("click", () => setScopeChecks(kind, false));
  });
  if (profileSelect) profileSelect.addEventListener("change", loadScope);
  if (runForm) {
    runForm.addEventListener("submit", (event) => {
      const selectedServices = serviceChecks.filter((item) => item.checked).length;
      if (!selectedServices) return;
      for (const kind of scopeKinds) {
        const manual = document.querySelector(`[data-scope-manual="${kind}"]`);
        const manualValue = manual ? manual.value.trim() : "";
        const checks = Array.from(document.querySelectorAll(`[data-scope-checkbox="${kind}"]`));
        if (!manualValue && checks.length && !checks.some((item) => item.checked)) {
          event.preventDefault();
          if (scopeStatus) scopeStatus.textContent = `${kind}는 최소 1개 이상 선택해야 합니다.`;
          return;
        }
      }
    });
  }
  refreshCount();
  loadScope();
})();
</script>
"""


def _job_refresh_script(job_id):
    script = """
<script>
const jobId = __JOB_ID__;
let latestEvents = [];
let activeLogFilter = "all";
function cell(value) {
  return String(value === null || value === undefined || value === "" ? "-" : value);
}
function esc(value) {
  return cell(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[ch]));
}
function statusClass(value) {
  const normalized = cell(value).toLowerCase();
  if (["queued", "running", "completed", "failed"].includes(normalized)) {
    return `status-${normalized}`;
  }
  return "status-unknown";
}
function levelClass(value) {
  const normalized = cell(value).toLowerCase();
  if (["info", "warn", "warning", "error"].includes(normalized)) {
    return `level-${normalized}`;
  }
  return "level-other";
}
function healthClass(value) {
  const normalized = cell(value).toLowerCase().replace(/_/g, "-");
  if (["ok", "partial", "permission-limited", "failed", "no-data"].includes(normalized)) {
    return `health-${normalized}`;
  }
  return "health-unknown";
}
function summarize(events) {
  return events.reduce((summary, event) => {
    const level = cell(event.level).toUpperCase();
    if (level === "WARN" || level === "WARNING") summary.warnings += 1;
    if (level === "ERROR") summary.errors += 1;
    if (event.kind === "permission_denied") summary.permissionDenied += 1;
    if (event.event === "step_end") {
      const collected = Number(event.collected || 0);
      if (!Number.isNaN(collected)) summary.collected += collected;
    }
    summary.events += 1;
    return summary;
  }, { events: 0, warnings: 0, permissionDenied: 0, errors: 0, collected: 0 });
}
function setText(selector, value) {
  const node = document.querySelector(selector);
  if (node) node.textContent = cell(value);
}
function updateProgress(job) {
  const bar = document.querySelector("[data-progress-bar]");
  if (!bar) return;
  const active = job.status === "running" || job.status === "queued";
  bar.classList.toggle("is-active", active);
  const percent = Number(job.progress_percent);
  if (!Number.isNaN(percent)) {
    bar.style.width = `${Math.max(0, Math.min(100, percent))}%`;
    return;
  }
  bar.style.width = active ? "20%" : "0";
}
function eventMatchesFilter(event) {
  const level = cell(event.level).toUpperCase();
  const query = (document.querySelector("[data-log-search]")?.value || "").trim().toLowerCase();
  if (activeLogFilter === "warn" && level !== "WARN" && level !== "WARNING") return false;
  if (activeLogFilter === "error" && level !== "ERROR") return false;
  if (activeLogFilter === "permission" && event.kind !== "permission_denied") return false;
  if (!query) return true;
  return [
    event.timestamp,
    event.level,
    event.event,
    event.step_service || event.service,
    event.step_region || event.region,
    event.compartment,
    event.resource,
    event.kind,
    event.status,
    event.code,
    event.message,
    event.detail
  ].some((value) => cell(value).toLowerCase().includes(query));
}
function renderEvents() {
  const events = latestEvents.filter(eventMatchesFilter);
  const rows = events.slice(-100).reverse().map((event) => {
    const service = event.step_service || event.service;
    const region = event.step_region || event.region;
    const message = event.message || event.detail || "";
    return `
      <tr>
        <td>${esc(event.timestamp)}</td>
        <td><span class="level-badge ${levelClass(event.level)}">${esc(event.level)}</span></td>
        <td>${esc(event.event)}</td>
        <td>${esc(service)}</td>
        <td>${esc(region)}</td>
        <td>${esc(event.kind)}</td>
        <td>${esc(event.code || event.status)}</td>
        <td>${esc(event.collected)}</td>
        <td>${esc(message)}</td>
      </tr>
    `;
  }).join("");
  document.querySelector("[data-events]").innerHTML =
    rows || `<tr><td class="empty-cell" colspan="9">표시할 이벤트가 없습니다.</td></tr>`;
  setText("[data-visible-event-count]", events.length);
}
function renderResults(results) {
  const target = document.querySelector("[data-results]");
  if (!target) return;
  const rows = results.map((result) => `
    <tr>
      <td>${esc(result.service)}</td>
      <td>${esc(result.region)}</td>
      <td><span class="health-badge ${healthClass(result.health)}">${esc(result.health)}</span></td>
      <td>${esc(result.collected)}</td>
      <td>${esc(result.warning_count)}</td>
      <td>${esc(result.permission_denied_count)}</td>
      <td>${esc(result.errors)}</td>
      <td>${esc(result.skipped)}</td>
      <td>${esc(result.duration_ms)}</td>
      <td>${esc(result.output_path || result.detail || "")}</td>
    </tr>
  `).join("");
  target.innerHTML = rows || `<tr><td class="empty-cell" colspan="10">완료 후 서비스 결과가 표시됩니다.</td></tr>`;
}
async function copyImportantLogs() {
  const rows = latestEvents
    .filter((event) => {
      const level = cell(event.level).toUpperCase();
      return level === "WARN" || level === "WARNING" || level === "ERROR";
    })
    .map((event) => [
      event.timestamp,
      event.level,
      event.event,
      event.step_service || event.service,
      event.step_region || event.region,
      event.compartment,
      event.resource,
      event.status,
      event.code,
      event.message || event.detail || ""
    ].map(cell).join(" | "));

  const button = document.querySelector("[data-copy-important-logs]");
  if (!rows.length) {
    if (button) button.textContent = "복사할 WARN/ERROR 없음";
    return;
  }

  try {
    await navigator.clipboard.writeText(rows.join("\\n"));
    if (button) button.textContent = "복사 완료";
  } catch (error) {
    if (button) button.textContent = "복사 실패";
  }
  setTimeout(() => {
    if (button) button.textContent = "WARN/ERROR 복사";
  }, 1800);
}
async function refreshJob() {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) return;
  const job = await response.json();
  const status = document.querySelector("[data-status]");
  if (status) {
    status.textContent = cell(job.status);
    status.className = `status-badge ${statusClass(job.status)}`;
  }
  setText("[data-current-step]", job.current_step);
  setText("[data-duration]", job.duration);
  setText("[data-completed-steps]", job.completed_steps);
  setText("[data-progress-label]", job.progress_label);
  setText("[data-progress-percent]", `${job.progress_percent}%`);
  setText("[data-started-at]", job.started_at);
  setText("[data-finished-at]", job.finished_at);
  const summary = summarize(job.events || []);
  const runSummary = job.run_summary || {};
  setText("[data-event-count]", summary.events);
  setText("[data-warning-count]", runSummary.warning_count ?? summary.warnings);
  setText("[data-permission-denied-count]", runSummary.permission_denied_count ?? summary.permissionDenied);
  setText("[data-error-count]", runSummary.error_count ?? summary.errors);
  setText("[data-collected-count]", summary.collected);
  updateProgress(job);

  const download = document.querySelector("[data-download]");
  if (download) {
    download.hidden = !(job.status === "completed" && job.report_exists);
  }
  const errorBox = document.querySelector("[data-error]");
  if (errorBox) {
    errorBox.hidden = !job.error;
    errorBox.textContent = job.error || "";
  }
  renderResults(job.service_results || []);
  latestEvents = job.events || [];
  renderEvents();
  if (job.status === "running" || job.status === "queued") {
    setTimeout(refreshJob, 3000);
  }
}
document.querySelectorAll("[data-log-filter]").forEach((button) => {
  button.addEventListener("click", () => {
    activeLogFilter = button.dataset.logFilter || "all";
    document.querySelectorAll("[data-log-filter]").forEach((item) => {
      item.classList.toggle("active", item === button);
    });
    renderEvents();
  });
});
const logSearch = document.querySelector("[data-log-search]");
if (logSearch) logSearch.addEventListener("input", renderEvents);
const copyLogs = document.querySelector("[data-copy-important-logs]");
if (copyLogs) copyLogs.addEventListener("click", copyImportantLogs);
refreshJob();
</script>
"""
    return script.replace("__JOB_ID__", repr(job_id))


def _layout(title, body, *, refresh_job_id=None, extra_script=""):
    refresh_script = _job_refresh_script(refresh_job_id) if refresh_job_id else ""
    return HTMLResponse(
        f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_safe(title)}</title>
  <style>{BASE_CSS}</style>
</head>
<body>
  <header class="app-header">
    <div class="header-inner">
      <div class="brand">
        <h1>OCI Resource Extractor</h1>
        <p>Raw JSON 보존과 Excel 리포트 생성을 위한 웹 실행 콘솔</p>
      </div>
      <div class="header-meta">
        <span class="chip">FastAPI</span>
        <span class="chip">Raw-first report</span>
      </div>
    </div>
  </header>
  <main>{body}</main>
  {extra_script}
  {refresh_script}
</body>
</html>"""
    )


def _render_service_option(service_name):
    label = _service_label(service_name)
    scope = _service_scope(service_name)
    return f"""<label class="service-option" data-service-option data-service-name="{_safe(service_name)}" data-service-label="{_safe(label)}">
  <input data-service-checkbox type="checkbox" name="services" value="{_safe(service_name)}" checked>
  <span>
    <span class="service-name">{_safe(label)}</span>
    <span class="service-key">{_safe(service_name)}</span>
  </span>
  <span class="scope-badge">{_safe(scope)}</span>
</label>"""


def _render_service_groups():
    registry_names = [service["name"] for service in SERVICE_REGISTRY]
    grouped_names = set()
    groups = []

    for group_name, service_names in SERVICE_GROUPS:
        items = [name for name in service_names if name in registry_names]
        if not items:
            continue
        grouped_names.update(items)
        options = "\n".join(_render_service_option(name) for name in items)
        groups.append(
            f"""<div class="service-group">
  <div class="service-group-title">
    <span>{_safe(group_name)}</span>
    <span>{len(items)}</span>
  </div>
  <div class="service-grid">{options}</div>
</div>"""
        )

    remaining = [name for name in registry_names if name not in grouped_names]
    if remaining:
        options = "\n".join(_render_service_option(name) for name in remaining)
        groups.append(
            f"""<div class="service-group">
  <div class="service-group-title">
    <span>Other</span>
    <span>{len(remaining)}</span>
  </div>
  <div class="service-grid">{options}</div>
</div>"""
        )

    return "\n".join(groups)


def _render_active_jobs(active_jobs):
    rows = []
    for job in active_jobs[:10]:
        rows.append(
            f"""<tr>
  <td><a class="job-link" href="/jobs/{_safe(job['id'])}">{_safe(job['id'])}</a></td>
  <td>{_safe(job.get('profile'))}</td>
  <td>{_status_badge(job.get('status'))}</td>
  <td>{_safe(job.get('current_step', '-'))}</td>
  <td>{_safe(_duration_text(job.get('started_ts'), job.get('finished_ts')) if job.get('started_ts') else '-')}</td>
  <td>{_safe(job.get('created_at', '-'))}</td>
</tr>"""
        )
    if not rows:
        return '<tr><td class="empty-cell" colspan="6">최근 작업이 없습니다.</td></tr>'
    return "\n".join(rows)


def _render_home(message=None):
    profiles = common.get_profiles()
    profile_options = "\n".join(
        f'<option value="{_safe(profile)}">{_safe(profile)}</option>' for profile in profiles
    )
    active_jobs = sorted(
        (_job_snapshot(job_id) for job_id in JOBS),
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )
    running_count = sum(1 for job in active_jobs if job.get("status") == "running")
    completed_count = sum(1 for job in active_jobs if job.get("status") == "completed")
    failed_count = sum(1 for job in active_jobs if job.get("status") == "failed")

    notice = f'<div class="notice">{_safe(message)}</div>' if message else ""
    disabled = "disabled" if not profiles else ""
    profile_select = (
        f'<select id="profile" name="profile" required>{profile_options}</select>'
        if profiles
        else '<select id="profile" name="profile" disabled><option>OCI profile 없음</option></select>'
    )
    active_rows = _render_active_jobs(active_jobs)
    service_groups = _render_service_groups()
    total_services = len(SERVICE_REGISTRY)

    body = f"""
{notice}
<div class="workspace-grid">
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>수집 실행</h2>
        <p>Profile과 수집 범위를 선택한 뒤 실행합니다.</p>
      </div>
      <span class="count-badge">{total_services} services</span>
    </div>
    <div class="panel-body">
      <form method="post" action="/jobs" data-run-form>
        <div class="field-grid">
          <div class="field">
            <label for="profile">OCI Profile</label>
            {profile_select}
            <p class="hint">~/.oci/config profile</p>
          </div>
          <div class="field field-wide">
            <label>Scope</label>
            <div class="scope-status" data-scope-status>Profile scope 조회 대기</div>
          </div>
        </div>
        <input id="regions" type="hidden" name="regions" data-scope-hidden="regions">
        <input id="compartments" type="hidden" name="compartments" data-scope-hidden="compartments">
        <div class="scope-grid">
          <div class="scope-block">
            <div class="scope-block-header">
              <span class="scope-block-title">Region 제한</span>
              <span class="count-badge" data-scope-count="regions">-</span>
              <div class="scope-controls">
                <button class="subtle" type="button" data-scope-select-all="regions">전체</button>
                <button class="subtle" type="button" data-scope-clear="regions">해제</button>
              </div>
            </div>
            <div class="scope-list" data-scope-list="regions">
              <div class="scope-status">Profile을 선택하면 조회합니다.</div>
            </div>
            <div class="manual-row">
              <label for="regions-manual">직접 입력</label>
              <input id="regions-manual" type="text" data-scope-manual="regions" placeholder="ap-seoul-1,ap-tokyo-1">
            </div>
          </div>
          <div class="scope-block">
            <div class="scope-block-header">
              <span class="scope-block-title">Compartment 제한</span>
              <span class="count-badge" data-scope-count="compartments">-</span>
              <div class="scope-controls">
                <button class="subtle" type="button" data-scope-select-all="compartments">전체</button>
                <button class="subtle" type="button" data-scope-clear="compartments">해제</button>
              </div>
            </div>
            <div class="scope-list" data-scope-list="compartments">
              <div class="scope-status">Profile을 선택하면 조회합니다.</div>
            </div>
            <div class="manual-row">
              <label for="compartments-manual">직접 입력</label>
              <input id="compartments-manual" type="text" data-scope-manual="compartments" placeholder="network-dev,app-dev">
            </div>
          </div>
        </div>

        <div class="section-divider"></div>

        <div class="service-toolbar">
          <div class="service-tools">
            <label for="service-filter">서비스 검색</label>
            <input id="service-filter" type="text" data-service-filter placeholder="compute, dns, waf">
          </div>
          <div class="button-group">
            <button class="subtle" type="button" data-select-all>전체 선택</button>
            <button class="subtle" type="button" data-clear-services>선택 해제</button>
          </div>
        </div>
        <div class="status-topline">
          <h2 style="margin:0;font-size:16px;">서비스 선택</h2>
          <span class="count-badge" data-selected-count>0 selected</span>
        </div>
        {service_groups}

        <div class="actions">
          <button type="submit" {disabled}>{_icon('play')}수집 시작</button>
          <a class="button secondary" href="/">{_icon('refresh')}새로고침</a>
        </div>
      </form>
    </div>
  </section>

  <div class="stack">
    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>작업 현황</h2>
          <p>현재 프로세스에 보관된 최근 작업</p>
        </div>
      </div>
      <div class="panel-body">
        <div class="summary-strip">
          <div class="summary-item"><span>Total</span><strong>{len(active_jobs)}</strong></div>
          <div class="summary-item"><span>Running</span><strong>{running_count}</strong></div>
          <div class="summary-item"><span>Completed</span><strong>{completed_count}</strong></div>
          <div class="summary-item"><span>Failed</span><strong>{failed_count}</strong></div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-header">
        <div>
          <h2>최근 작업</h2>
          <p>작업 상세에서 이벤트 로그와 다운로드를 확인합니다.</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Job ID</th>
              <th>Profile</th>
              <th>Status</th>
              <th>Current Step</th>
              <th>Duration</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>{active_rows}</tbody>
        </table>
      </div>
    </section>
  </div>
</div>
"""
    return _layout("OCI Resource Extractor", body, extra_script=_home_script())


@app.get("/", response_class=HTMLResponse)
def home():
    return _render_home()


@app.get("/api/profiles/{profile}/scope")
def profile_scope(profile):
    if profile not in common.get_profiles():
        return JSONResponse({"error": "Profile not found"}, status_code=404)

    try:
        client = common.OCIClient(profile)
    except Exception as exc:
        return JSONResponse(
            {"error": "Profile scope lookup failed", "detail": str(exc)},
            status_code=500,
        )

    compartments = []
    for compartment in client.compartments:
        compartments.append(
            {
                "id": getattr(compartment, "id", ""),
                "name": getattr(compartment, "name", ""),
                "description": getattr(compartment, "description", ""),
            }
        )

    compartments.sort(key=lambda item: (item["name"].lower(), item["id"]))
    return {
        "profile": profile,
        "tenancy_name": client.tenancy_name,
        "tenancy_id": client.tenancy_id,
        "regions": sorted(client.regions),
        "compartments": compartments,
    }


@app.post("/jobs")
async def create_job(request: Request):
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    profile = (form.get("profile") or [""])[0].strip()
    regions = (form.get("regions") or [""])[0].strip()
    compartments = (form.get("compartments") or [""])[0].strip()
    service_names = [item.strip() for item in form.get("services", []) if item.strip()]

    if not profile:
        return _render_home("OCI profile을 선택해야 합니다.")

    if profile not in common.get_profiles():
        return _render_home("선택한 OCI profile을 찾을 수 없습니다.")

    if not service_names:
        return _render_home("최소 1개 이상의 서비스를 선택해야 합니다.")

    if not JOB_LOCK.acquire(blocking=False):
        return _render_home("이미 실행 중인 수집 작업이 있습니다. 현재 작업이 끝난 뒤 다시 실행하세요.")

    job_id = uuid.uuid4().hex[:12]
    with STORE_LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "profile": profile,
            "regions": regions,
            "compartments": compartments,
            "services": service_names,
            "status": "queued",
            "current_step": "queued",
            "created_at": _now(),
            "started_at": None,
            "finished_at": None,
            "started_ts": None,
            "finished_ts": None,
            "completed_steps": 0,
            "total_steps": None,
            "report_path": None,
            "json_paths": {},
            "service_results": [],
            "run_summary": {},
            "diagnostics": [],
            "events": [],
            "error": "",
        }

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, profile, regions, compartments, service_names),
        daemon=True,
    )
    thread.start()
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


def _render_job_chips(job):
    chips = []
    for service_name in job.get("services", []):
        chips.append(f'<span class="chip">{_safe(_service_label(service_name))}</span>')
    if not chips:
        return '<span class="chip">-</span>'
    return "\n".join(chips)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id):
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    events = job.get("events", [])
    summary = _event_summary(events)
    run_summary = job.get("run_summary") or {}
    warning_count = run_summary.get("warning_count", summary["warnings"])
    permission_denied_count = run_summary.get(
        "permission_denied_count",
        summary["permission_denied"],
    )
    error_count = run_summary.get("error_count", summary["errors"])
    progress = _progress_details(job)
    download_hidden = "" if job.get("status") == "completed" and job.get("report_path") else "hidden"
    error_hidden = "" if job.get("error") else "hidden"
    scope_text = (
        f"{len(_normalize_filter_values(job.get('regions')))} region filter"
        if _normalize_filter_values(job.get("regions"))
        else "all subscribed regions"
    )
    compartment_text = (
        f"{len(_normalize_filter_values(job.get('compartments')))} compartment filter"
        if _normalize_filter_values(job.get("compartments"))
        else "all active compartments"
    )

    body = f"""
<div class="stack">
  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>작업 상태</h2>
        <p>{_safe(job_id)} / {_safe(job.get('profile'))}</p>
      </div>
      <span data-status class="status-badge {_safe(_status_class(job.get('status')))}">{_safe(job.get('status'))}</span>
    </div>
    <div class="panel-body status-panel">
      <div class="progress-meta">
        <span>Progress</span>
        <strong><span data-progress-label>{_safe(progress['progress_label'])}</span> (<span data-progress-percent>{_safe(progress['progress_percent'])}%</span>)</strong>
      </div>
      <div class="progress-track"><div class="progress-bar" data-progress-bar></div></div>
      <div class="metric-grid">
        <div class="metric"><span>Current Step</span><strong data-current-step>{_safe(job.get('current_step', '-'))}</strong></div>
        <div class="metric"><span>Completed Steps</span><strong data-completed-steps>{_safe(job.get('completed_steps', 0))}</strong></div>
        <div class="metric"><span>Duration</span><strong data-duration>{_safe(_duration_text(job.get('started_ts'), job.get('finished_ts')))}</strong></div>
        <div class="metric"><span>Scope</span><strong>{_safe(scope_text)}</strong></div>
        <div class="metric"><span>Compartments</span><strong>{_safe(compartment_text)}</strong></div>
        <div class="metric"><span>Started</span><strong data-started-at>{_safe(job.get('started_at', '-'))}</strong></div>
        <div class="metric"><span>Finished</span><strong data-finished-at>{_safe(job.get('finished_at', '-'))}</strong></div>
        <div class="metric"><span>Selected Services</span><strong>{len(job.get('services', []))}</strong></div>
      </div>
      <div class="summary-strip">
        <div class="summary-item"><span>Events</span><strong data-event-count>{summary['events']}</strong></div>
        <div class="summary-item"><span>Collected Rows</span><strong data-collected-count>{summary['collected']}</strong></div>
        <div class="summary-item"><span>Warnings</span><strong data-warning-count>{warning_count}</strong></div>
        <div class="summary-item"><span>Permission Denied</span><strong data-permission-denied-count>{permission_denied_count}</strong></div>
        <div class="summary-item"><span>Errors</span><strong data-error-count>{error_count}</strong></div>
      </div>
      <div class="chip-row">{_render_job_chips(job)}</div>
      <div class="actions">
        <a class="button secondary" href="/">{_icon('back')}작업 목록</a>
        <a class="button" data-download {download_hidden} href="/jobs/{_safe(job_id)}/download">{_icon('download')}Excel 다운로드</a>
      </div>
      <div class="error-box" data-error {error_hidden}>{_safe(job.get('error'))}</div>
    </div>
  </section>

  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>서비스 결과</h2>
        <p>완료된 서비스별 수집 결과</p>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Region</th>
            <th>Health</th>
            <th>Collected</th>
            <th>Warnings</th>
            <th>Permission Denied</th>
            <th>Errors</th>
            <th>Skipped</th>
            <th>Duration ms</th>
            <th>Output</th>
          </tr>
        </thead>
        <tbody data-results>
          <tr><td class="empty-cell" colspan="10">완료 후 서비스 결과가 표시됩니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <div class="panel-header">
      <div>
        <h2>이벤트 로그</h2>
        <p>최근 이벤트 100개 / 표시 <span data-visible-event-count>{len(events)}</span>개</p>
      </div>
    </div>
    <div class="log-toolbar">
      <div class="segmented" aria-label="Log level filter">
        <button class="active" type="button" data-log-filter="all">전체</button>
        <button type="button" data-log-filter="permission">Permission</button>
        <button type="button" data-log-filter="warn">WARN</button>
        <button type="button" data-log-filter="error">ERROR</button>
      </div>
      <input class="log-search" type="text" data-log-search placeholder="service, region, event, message 검색">
      <button class="subtle" type="button" data-copy-important-logs>WARN/ERROR 복사</button>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Level</th>
            <th>Event</th>
            <th>Service</th>
            <th>Region</th>
            <th>Kind</th>
            <th>Code</th>
            <th>Count</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody data-events>
          <tr><td class="empty-cell" colspan="9">이벤트를 불러오는 중입니다.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</div>
"""
    return _layout(f"Job {job_id}", body, refresh_job_id=job_id)


@app.get("/api/jobs/{job_id}")
def job_status(job_id):
    job = _job_snapshot(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    report_path = job.get("report_path")
    started_ts = job.get("started_ts")
    finished_ts = job.get("finished_ts")
    progress = _progress_details(job)
    return {
        "id": job["id"],
        "profile": job["profile"],
        "status": job["status"],
        "current_step": job.get("current_step"),
        "completed_steps": job.get("completed_steps", 0),
        "total_steps": progress["total_steps"],
        "progress_percent": progress["progress_percent"],
        "progress_label": progress["progress_label"],
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "duration": _duration_text(started_ts, finished_ts) if started_ts else "-",
        "report_path": report_path,
        "report_exists": bool(report_path and os.path.exists(report_path)),
        "events": job.get("events", []),
        "service_results": job.get("service_results", []),
        "run_summary": job.get("run_summary", {}),
        "diagnostics": job.get("diagnostics", []),
        "error": job.get("error", ""),
    }


@app.get("/jobs/{job_id}/download")
def download_report(job_id):
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job is not completed")

    report_path = job.get("report_path")
    if not report_path:
        raise HTTPException(status_code=404, detail="Report path is missing")

    path = Path(report_path).resolve()
    report_root = Path("OCI_Reports").resolve()
    if report_root not in path.parents or not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    return FileResponse(
        path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
