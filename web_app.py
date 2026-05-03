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


def _layout(title, body, *, refresh_job_id=None):
    refresh_script = ""
    if refresh_job_id:
        refresh_script = f"""
<script>
const jobId = {refresh_job_id!r};
function cell(value) {{
  return String(value === null || value === undefined || value === "" ? "-" : value);
}}
function esc(value) {{
  return cell(value).replace(/[&<>"']/g, (ch) => ({{
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }}[ch]));
}}
async function refreshJob() {{
  const response = await fetch(`/api/jobs/${{jobId}}`);
  if (!response.ok) return;
  const job = await response.json();
  document.querySelector("[data-status]").textContent = job.status;
  document.querySelector("[data-current-step]").textContent = cell(job.current_step);
  document.querySelector("[data-duration]").textContent = cell(job.duration);
  document.querySelector("[data-completed-steps]").textContent = cell(job.completed_steps);
  const download = document.querySelector("[data-download]");
  if (job.status === "completed" && job.report_exists) {{
    download.hidden = false;
  }}
  if (job.error) {{
    const errorBox = document.querySelector("[data-error]");
    errorBox.hidden = false;
    errorBox.textContent = job.error;
  }}
  const rows = job.events.slice(-80).reverse().map((event) => `
    <tr>
      <td>${{esc(event.timestamp)}}</td>
      <td>${{esc(event.level)}}</td>
      <td>${{esc(event.event)}}</td>
      <td>${{esc(event.step_service || event.service)}}</td>
      <td>${{esc(event.step_region || event.region)}}</td>
      <td>${{esc(event.collected)}}</td>
      <td>${{esc(event.message || event.detail || "")}}</td>
    </tr>
  `).join("");
  document.querySelector("[data-events]").innerHTML = rows || `<tr><td colspan="7">아직 이벤트가 없습니다.</td></tr>`;
  if (job.status === "running" || job.status === "queued") {{
    setTimeout(refreshJob, 3000);
  }}
}}
refreshJob();
</script>
"""

    return HTMLResponse(
        f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_safe(title)}</title>
  <style>
    :root {{
      --bg: #f7f8fa;
      --panel: #ffffff;
      --line: #d9dde5;
      --text: #18202f;
      --muted: #667085;
      --accent: #1867c0;
      --accent-dark: #0f4f9a;
      --warn: #9a5b00;
      --error: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.5;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
      padding: 18px 28px;
    }}
    header h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    header p {{
      margin: 4px 0 0;
      color: var(--muted);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 18px;
    }}
    h2 {{
      font-size: 16px;
      margin: 0 0 14px;
    }}
    label {{
      display: block;
      font-weight: 600;
      margin-bottom: 6px;
    }}
    input, select {{
      width: 100%;
      height: 38px;
      border: 1px solid #c9ced8;
      border-radius: 6px;
      padding: 7px 10px;
      background: #ffffff;
      color: var(--text);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .service-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px 14px;
    }}
    .check {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
      margin: 0;
    }}
    .check input {{
      width: 16px;
      height: 16px;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      align-items: center;
      margin-top: 16px;
    }}
    button, .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: #ffffff;
      padding: 8px 14px;
      font-weight: 700;
      text-decoration: none;
      cursor: pointer;
    }}
    button:hover, .button:hover {{
      background: var(--accent-dark);
      border-color: var(--accent-dark);
    }}
    .button.secondary {{
      background: #ffffff;
      color: var(--accent);
    }}
    .button.secondary:hover {{
      background: #eef5ff;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fbfcfe;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
    }}
    .metric strong {{
      display: block;
      margin-top: 3px;
      font-size: 15px;
      word-break: break-word;
    }}
    .hint {{
      color: var(--muted);
      margin: 4px 0 0;
    }}
    .error {{
      border-color: #f1b8b8;
      color: var(--error);
      background: #fff7f7;
      padding: 10px;
      border-radius: 6px;
      margin-top: 12px;
      white-space: pre-wrap;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      text-align: left;
      padding: 8px;
      vertical-align: top;
    }}
    th {{
      background: #eef2f7;
      font-weight: 700;
    }}
    td {{
      word-break: break-word;
    }}
    @media (max-width: 860px) {{
      main {{ padding: 16px; }}
      .grid, .service-grid, .meta {{ grid-template-columns: 1fr; }}
      header {{ padding: 16px; }}
      .actions {{ flex-direction: column; align-items: stretch; }}
      button, .button {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>OCI Resource Extractor</h1>
    <p>OCI 리소스를 수집하고 raw JSON과 Excel 리포트를 생성합니다.</p>
  </header>
  <main>{body}</main>
  {refresh_script}
</body>
</html>"""
    )


def _render_home(message=None):
    profiles = common.get_profiles()
    service_checks = "\n".join(
        f"""<label class="check">
  <input type="checkbox" name="services" value="{_safe(svc['name'])}" checked>
  <span>{_safe(svc['name'])}</span>
</label>"""
        for svc in SERVICE_REGISTRY
    )
    profile_options = "\n".join(
        f'<option value="{_safe(profile)}">{_safe(profile)}</option>' for profile in profiles
    )
    active_jobs = sorted(
        (_job_snapshot(job_id) for job_id in JOBS),
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )
    active_rows = "\n".join(
        f"""<tr>
  <td><a href="/jobs/{_safe(job['id'])}">{_safe(job['id'])}</a></td>
  <td>{_safe(job.get('profile'))}</td>
  <td>{_safe(job.get('status'))}</td>
  <td>{_safe(job.get('current_step', '-'))}</td>
  <td>{_safe(job.get('created_at', '-'))}</td>
</tr>"""
        for job in active_jobs[:10]
    )
    if not active_rows:
        active_rows = '<tr><td colspan="5">최근 작업이 없습니다.</td></tr>'

    notice = f'<section class="error">{_safe(message)}</section>' if message else ""
    disabled = "disabled" if not profiles else ""
    profile_select = (
        f'<select name="profile" required>{profile_options}</select>'
        if profiles
        else '<select name="profile" disabled><option>OCI profile 없음</option></select>'
    )
    body = f"""
{notice}
<section>
  <h2>수집 실행</h2>
  <form method="post" action="/jobs">
    <div class="grid">
      <div>
        <label for="profile">OCI Profile</label>
        {profile_select}
        <p class="hint">`~/.oci/config`에 등록된 profile입니다.</p>
      </div>
      <div>
        <label for="regions">Region 제한</label>
        <input id="regions" name="regions" placeholder="예: ap-seoul-1,ap-tokyo-1">
        <p class="hint">비워두면 profile의 전체 구독 리전을 조회합니다.</p>
      </div>
      <div>
        <label for="compartments">Compartment 제한</label>
        <input id="compartments" name="compartments" placeholder="예: network-dev,app-dev">
        <p class="hint">컴파트먼트 이름 기준이며, 비워두면 전체 활성 컴파트먼트를 조회합니다.</p>
      </div>
    </div>
    <h2 style="margin-top:18px;">서비스 선택</h2>
    <div class="service-grid">
      {service_checks}
    </div>
    <div class="actions">
      <button type="submit" {disabled}>수집 시작</button>
      <a class="button secondary" href="/">새로고침</a>
    </div>
  </form>
</section>
<section>
  <h2>최근 작업</h2>
  <table>
    <thead>
      <tr>
        <th>Job ID</th>
        <th>Profile</th>
        <th>Status</th>
        <th>Current Step</th>
        <th>Created</th>
      </tr>
    </thead>
    <tbody>{active_rows}</tbody>
  </table>
</section>
"""
    return _layout("OCI Resource Extractor", body)


@app.get("/", response_class=HTMLResponse)
def home():
    return _render_home()


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
            "report_path": None,
            "json_paths": {},
            "service_results": [],
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


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id):
    job = _job_snapshot(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    download_hidden = "" if job.get("status") == "completed" and job.get("report_path") else "hidden"
    error_hidden = "" if job.get("error") else "hidden"
    body = f"""
<section>
  <h2>작업 상태</h2>
  <div class="meta">
    <div class="metric"><span>Job ID</span><strong>{_safe(job_id)}</strong></div>
    <div class="metric"><span>Status</span><strong data-status>{_safe(job.get('status'))}</strong></div>
    <div class="metric"><span>Profile</span><strong>{_safe(job.get('profile'))}</strong></div>
    <div class="metric"><span>Duration</span><strong data-duration>{_safe(_duration_text(job.get('started_ts'), job.get('finished_ts')))}</strong></div>
    <div class="metric"><span>Current Step</span><strong data-current-step>{_safe(job.get('current_step', '-'))}</strong></div>
    <div class="metric"><span>Completed Steps</span><strong data-completed-steps>{_safe(job.get('completed_steps', 0))}</strong></div>
    <div class="metric"><span>Regions</span><strong>{_safe(_csv_text(job.get('regions')))}</strong></div>
    <div class="metric"><span>Compartments</span><strong>{_safe(_csv_text(job.get('compartments')))}</strong></div>
  </div>
  <div class="actions">
    <a class="button secondary" href="/">작업 목록</a>
    <a class="button" data-download {download_hidden} href="/jobs/{_safe(job_id)}/download">Excel 다운로드</a>
  </div>
  <div class="error" data-error {error_hidden}>{_safe(job.get('error'))}</div>
</section>
<section>
  <h2>이벤트 로그</h2>
  <table>
    <thead>
      <tr>
        <th>Time</th>
        <th>Level</th>
        <th>Event</th>
        <th>Service</th>
        <th>Region</th>
        <th>Count</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody data-events>
      <tr><td colspan="7">이벤트를 불러오는 중입니다.</td></tr>
    </tbody>
  </table>
</section>
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
    return {
        "id": job["id"],
        "profile": job["profile"],
        "status": job["status"],
        "current_step": job.get("current_step"),
        "completed_steps": job.get("completed_steps", 0),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "duration": _duration_text(started_ts, finished_ts) if started_ts else "-",
        "report_path": report_path,
        "report_exists": bool(report_path and os.path.exists(report_path)),
        "events": job.get("events", []),
        "service_results": job.get("service_results", []),
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
