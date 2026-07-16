import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

from django.http import StreamingHttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .apply_sessions import close_apply_session, drive_apply_session, fill_apply_session, get_apply_session, handoff_apply_session, open_apply_session
from .paths import root_path
from .services import (
    add_followup_log,
    add_offers_to_pipeline,
    build_run_prompt,
    count_reports,
    detect_clis,
    discovery_dedup_lines,
    doctor_state,
    known_discovery_urls,
    pipeline_summary,
    read_memory,
    remember_fact,
    resolve_cli,
    run_node_script,
    write_temp_portals,
)


OUTPUT_CONTRACT = """

--- OUTPUT CONTRACT (the career-ops WEB is parsing your stream) ---
Follow modes/discover.md exactly. You are running headless for the web:
- You are a PROPOSER - never write a file (Write/Edit/Bash are disabled).
- Emit each candidate as ONE line, never inside a code fence:
  <<offer:{"url":"...","title":"...","company":"...","location":"...","source":"ai-search","why":"...","postedHint":"...","ats":"...","verification":"unconfirmed"}>>
  Valid JSON, one per line, the moment you're confident - stream them as you go.
- Between envelopes, narrate briefly (plain text) what you're searching - shown live as your reasoning.
- Be frugal (~3-6 searches, stop at a strong set). EVERY candidate is UNVERIFIED.
- Be a GENEROUS FINDER, not a judge: when a constraint (location, seniority, stage) can't be confirmed from the shallow signal, INCLUDE + flag the uncertainty in "why" - don't discard. NEVER score or judge fit; the A-F evaluation does that later, with the full JD.
- DEDUP: skip anything already known below; don't re-propose the user's existing companies.
"""


def extract_json_object(text: str) -> tuple[dict | None, bool]:
    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    start = cleaned.find("{")
    if start == -1:
        return None, False

    depth = 0
    in_str = False
    escaped = False
    end = -1
    for i, char in enumerate(cleaned[start:], start):
        if in_str:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_str = False
        elif char == '"':
            in_str = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    if end != -1:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            return (parsed, False) if isinstance(parsed, dict) else (None, False)
        except json.JSONDecodeError:
            pass

    fragment = cleaned[start:]
    pad = "}" * max(0, fragment.count("{") - fragment.count("}"))
    try_end = len(fragment)
    while try_end > 1:
        candidate = re.sub(r",\s*$", "", fragment[:try_end]) + pad
        try:
            parsed = json.loads(candidate)
            return (parsed, True) if isinstance(parsed, dict) else (None, True)
        except json.JSONDecodeError:
            previous_comma = fragment.rfind(",", 0, try_end - 1)
            if previous_comma <= 0:
                break
            try_end = previous_comma
    return None, True


class DoctorView(APIView):
    def get(self, request):
        return Response(doctor_state())


class VersionView(APIView):
    def get(self, request):
        try:
            core_version = root_path("VERSION").read_text(encoding="utf-8").split()[0].strip()
        except FileNotFoundError:
            core_version = ""
        try:
            pkg = json.loads(root_path("web", "package.json").read_text(encoding="utf-8"))
            web_version = pkg.get("version") if isinstance(pkg.get("version"), str) else ""
        except Exception:
            web_version = ""
        try:
            sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=root_path(), stderr=subprocess.DEVNULL, text=True).strip()
        except Exception:
            sha = ""
        match = re.search(r"-(rc|beta|alpha|next)\b", core_version, re.IGNORECASE)
        channel = match.group(1).lower() if match else "alpha" if web_version.startswith("0.") else "stable"
        version = f"web {web_version}" if web_version else core_version
        return Response({"version": version, "coreVersion": core_version, "channel": channel, "sha": sha})


class WhatsNewView(APIView):
    def get(self, request):
        try:
            content = root_path("CHANGELOG.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            content = ""
        return Response({"content": content[:12000]})


class ClisView(APIView):
    def get(self, request):
        return Response({"clis": detect_clis()})


class FollowupsView(APIView):
    def get(self, request):
        try:
            result = run_node_script("followup-cadence", "--json", timeout=12)
        except FileNotFoundError:
            return Response({"available": False, "metadata": None, "entries": []})
        if result.returncode != 0 and not result.stdout:
            return Response({"available": False, "metadata": None, "entries": []})
        try:
            start = result.stdout.index("{")
            data = json.loads(result.stdout[start:])
            entries = data.get("entries") if isinstance(data.get("entries"), list) else []
            overdue = [entry for entry in entries if re.search(r"overdue|urgent", str(entry.get("status") or entry.get("urgency") or ""), re.IGNORECASE)][:8]
            top = (overdue or entries)[:6]
            return Response({"available": True, "metadata": data.get("metadata"), "entries": top})
        except Exception:
            return Response({"available": False, "metadata": None, "entries": []})


def claude_projects_dir() -> Path:
    configured = os.environ.get("CAREER_OPS_CLAUDE_PROJECTS_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".claude" / "projects"


def iter_jsonl_files(root: Path):
    try:
        yield from root.rglob("*.jsonl")
    except OSError:
        return


def compute_usage() -> dict:
    now_ms = int(time.time() * 1000)
    window_5h = now_ms - 5 * 3600 * 1000
    window_7d = now_ms - 7 * 24 * 3600 * 1000
    cutoff_mtime = (window_7d - 3600 * 1000) / 1000
    tokens_5h = tokens_7d = messages_5h = messages_7d = 0

    for file_path in iter_jsonl_files(claude_projects_dir()):
        try:
            if file_path.stat().st_mtime < cutoff_mtime:
                continue
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if '"usage"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = (event.get("message") or {}).get("usage")
            timestamp = event.get("timestamp")
            if not isinstance(usage, dict) or not isinstance(timestamp, str):
                continue
            try:
                from datetime import datetime

                ts_ms = int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() * 1000)
            except Exception:
                continue
            if ts_ms < window_7d:
                continue
            tokens = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
            tokens_7d += tokens
            messages_7d += 1
            if ts_ms >= window_5h:
                tokens_5h += tokens
                messages_5h += 1
    return {
        "window5h": {"tokens": tokens_5h, "messages": messages_5h},
        "window7d": {"tokens": tokens_7d, "messages": messages_7d},
        "computedAt": now_ms,
    }


class UsageView(APIView):
    def get(self, request):
        return Response(compute_usage())


def line_count(rel: str, predicate) -> int:
    try:
        return sum(1 for line in root_path(*rel.split("/")).read_text(encoding="utf-8").splitlines() if predicate(line))
    except FileNotFoundError:
        return 0


def dir_count(rel: str, ext: str) -> int:
    try:
        return sum(1 for child in root_path(rel).iterdir() if child.name.endswith(ext))
    except FileNotFoundError:
        return 0


def scanner_supports_json() -> bool:
    try:
        src = root_path("scan-ats-full.mjs").read_text(encoding="utf-8")
        return "--json" in src and "capHit" in src
    except FileNotFoundError:
        return False


def tracker_can_delete() -> bool:
    try:
        src = root_path("tracker.mjs").read_text(encoding="utf-8")
        return "delete" in src and "--num" in src
    except FileNotFoundError:
        return False


class ReportShapeView(APIView):
    def get(self, request):
        doctor = doctor_state()
        summary = pipeline_summary()
        inbox_candidates = line_count("data/pipeline.md", lambda line: re.match(r"^\s*-\s*\[[ xX]\]", line) is not None)
        tracker_candidates = line_count(
            "data/applications.md",
            lambda line: line.strip().startswith("|")
            and not re.match(r"^\|\s*#\s*\|", line.strip())
            and not re.match(r"^\|\s*:?-{2,}", line.strip()),
        )
        return Response(
            {
                "runtime": {"node": "", "python": platform.python_version(), "platform": platform.system().lower(), "arch": platform.machine()},
                "setup": {"phase": doctor["phase"], "missing": doctor["missing"], "hasCv": doctor["hasCv"], "hasData": doctor["hasData"]},
                "data": {
                    "inbox": {"candidates": inbox_candidates, "parsed": len(summary["inbox"])},
                    "tracker": {"candidates": tracker_candidates, "parsed": len(summary["applications"])},
                    "reports": dir_count("reports", ".md"),
                    "pdfs": dir_count("output", ".pdf"),
                    "followupsFile": root_path("data", "follow-ups.md").exists(),
                },
                "capabilities": {"scanJson": scanner_supports_json(), "trackerDelete": tracker_can_delete()},
            }
        )


class MemoryView(APIView):
    def get(self, request):
        return Response({"memory": read_memory()})

    def post(self, request):
        fact = str(request.data.get("fact") or "")
        if not fact.strip():
            return Response({"error": "fact required"}, status=400)
        try:
            result = remember_fact(fact)
        except Exception:
            return Response({"error": "write failed"}, status=500)
        return Response({"ok": True, "deduped": result == "deduped"})


class FollowupsLogView(APIView):
    def post(self, request):
        company = str(request.data.get("company") or "").strip()
        if not company:
            return Response({"error": "company required"}, status=400)
        try:
            add_followup_log(company=company, num=request.data.get("num"), note=str(request.data.get("note") or "Followed up"))
        except Exception as exc:
            return Response({"error": str(exc) or "write failed"}, status=500)
        return Response({"ok": True})


def clean_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:100]


def clean_explore_filters(data: dict) -> dict:
    ats = clean_list(data.get("ats")) or ["greenhouse", "lever", "ashby", "workday"]
    ats = [item for item in ats if item in {"greenhouse", "lever", "ashby", "workday"}] or ["greenhouse", "lever", "ashby", "workday"]

    def clamp(value, lo, hi, fallback):
        try:
            return max(lo, min(hi, round(float(value))))
        except Exception:
            return fallback

    return {
        "positive": clean_list(data.get("positive")),
        "negative": clean_list(data.get("negative")),
        "allow": clean_list(data.get("allow")),
        "block": clean_list(data.get("block")),
        "alwaysAllow": clean_list(data.get("alwaysAllow")),
        "sinceDays": clamp(data.get("sinceDays", data.get("since", 7)), 1, 60, 7),
        "limitPerAts": clamp(data.get("limitPerAts", data.get("limit", 150)), 50, 500, 150),
        "ats": ats,
    }


class ExploreAddView(APIView):
    def post(self, request):
        offers = request.data.get("offers")
        if not isinstance(offers, list):
            return Response({"added": 0, "error": "bad request"}, status=400)
        return Response(add_offers_to_pipeline(offers))


class ExploreKnownView(APIView):
    def get(self, request):
        return Response({"urls": sorted(known_discovery_urls())})


class ExploreAiView(APIView):
    def post(self, request):
        query = str(request.data.get("query") or "").strip()
        cli_id = str(request.data.get("cliId") or "").strip()
        if not query or not cli_id:
            return Response({"error": "query and cliId required"}, status=400)
        resolved = resolve_cli(cli_id)
        if not resolved:
            return Response({"error": f"CLI '{cli_id}' not found on this machine"}, status=404)
        try:
            mode = root_path("modes", "discover.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            return Response({"code": "MODE_MISSING", "error": "AI search needs a newer career-ops - update to enable it."}, status=400)

        memory = read_memory()
        memory_line = f"\n\nWHAT YOU KNOW ABOUT THE USER (persistent memory):\n{memory.strip()}" if memory.strip() else ""
        dedup_lines = discovery_dedup_lines()
        known_block = f"\n\n--- ALREADY KNOWN (dedup - do NOT propose these) ---\n" + "\n".join(dedup_lines) if dedup_lines else ""
        prompt = f"{mode}{OUTPUT_CONTRACT}{memory_line}{known_block}\n\n--- USER INTENT ---\n{query}\n"

        if cli_id == "claude":
            args = [
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--verbose",
                "--include-partial-messages",
                "--permission-mode",
                "acceptEdits",
                "--allowedTools",
                "Read,WebFetch,WebSearch,Glob,Grep",
                "--disallowedTools",
                "Bash,Write,Edit,NotebookEdit,Task",
            ]
        else:
            args = resolved["args"](prompt)

        def stream_text():
            emitted = False
            try:
                child = subprocess.Popen(
                    [resolved["path"], *args],
                    cwd=root_path(),
                    env=os.environ.copy(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except Exception as exc:
                yield f"\n[error launching {resolved['name']}: {exc}]\n"
                return

            try:
                if cli_id == "claude":
                    assert child.stdout is not None
                    for line in child.stdout:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") == "stream_event" and event.get("event", {}).get("type") == "content_block_delta":
                            text = event.get("event", {}).get("delta", {}).get("text")
                            if isinstance(text, str) and text:
                                emitted = True
                                yield text
                else:
                    assert child.stdout is not None
                    for chunk in child.stdout:
                        if chunk:
                            emitted = True
                            yield chunk
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                stderr = ""
                if child.stderr is not None:
                    try:
                        stderr = child.stderr.read()
                    except Exception:
                        stderr = ""
                if stderr and re.search(r"error|not found|denied|fatal", stderr, re.IGNORECASE):
                    yield f"\n[{resolved['name']}] {stderr.strip()}\n"
                if not emitted:
                    yield "_(no output - is the CLI authenticated?)_"
            finally:
                if child.poll() is None:
                    child.terminate()

        return StreamingHttpResponse(stream_text(), content_type="text/plain; charset=utf-8", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


class RunStreamView(APIView):
    def post(self, request):
        kind = str(request.data.get("kind") or "evaluate")
        input_text = str(request.data.get("input") or "").strip()
        cli_id = str(request.data.get("cliId") or "").strip()
        if not input_text or not cli_id:
            return Response({"error": "input and cliId required"}, status=400)
        resolved = resolve_cli(cli_id)
        if not resolved:
            return Response({"error": f"CLI '{cli_id}' not found"}, status=404)

        required = {"evaluate": "modes/oferta.md", "fix-portal": "verify-portals.mjs", "pdf": "generate-pdf.mjs"}.get(kind)
        if required and not root_path(*required.split("/")).exists():
            return Response({"error": f"This needs a complete career-ops checkout ({required}). CAREER_OPS_ROOT has data only - point it at a full checkout."}, status=400)
        if kind in {"evaluate", "pdf"} and not root_path("cv.md").exists():
            return Response({"error": "Add your CV first so I can score this against you - drop it on the home page."}, status=400)

        from datetime import date

        prompt = build_run_prompt(kind, input_text, read_memory(), date.today().isoformat())
        write_kind = kind in {"evaluate", "fix-portal", "pdf"}
        if cli_id == "claude":
            tools = (
                {"allowed": "Read,WebFetch,WebSearch,Write,Edit,Bash,Glob,Grep", "disallowed": "Task,NotebookEdit"}
                if write_kind
                else {"allowed": "Read,WebFetch,WebSearch,Glob,Grep", "disallowed": "Bash,Write,Edit,NotebookEdit,Task"}
            )
            args = [
                "-p",
                prompt,
                "--output-format",
                "stream-json",
                "--verbose",
                "--include-partial-messages",
                "--permission-mode",
                "acceptEdits",
                "--allowedTools",
                tools["allowed"],
                "--disallowedTools",
                tools["disallowed"],
            ]
        else:
            args = resolved["args"](prompt)

        reports_before = count_reports() if kind == "evaluate" else 0

        def ndjson_stream():
            def send(obj):
                return (json.dumps(obj) + "\n").encode("utf-8")

            emitted = False
            saw_error = False
            last_tokens = 0
            last_cost = None
            try:
                child = subprocess.Popen(
                    [resolved["path"], *args],
                    cwd=root_path(),
                    env=os.environ.copy(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except Exception as exc:
                yield send({"type": "error", "msg": str(exc)})
                return

            try:
                if cli_id == "claude":
                    assert child.stdout is not None
                    for line in child.stdout:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if event.get("type") == "stream_event":
                            ev = event.get("event") or {}
                            if ev.get("type") == "content_block_start" and (ev.get("content_block") or {}).get("type") == "tool_use":
                                yield send({"type": "tool", "name": (ev.get("content_block") or {}).get("name")})
                            elif ev.get("type") == "content_block_delta" and (ev.get("delta") or {}).get("text"):
                                emitted = True
                                yield send({"type": "text", "text": ev["delta"]["text"]})
                        elif event.get("type") == "system" and event.get("subtype") == "init":
                            yield send({"type": "status", "label": "Agent ready"})
                        elif event.get("type") == "result":
                            usage = event.get("usage") or {}
                            last_tokens = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0) + int(usage.get("cache_creation_input_tokens") or 0)
                            if isinstance(event.get("total_cost_usd"), (int, float)):
                                last_cost = event.get("total_cost_usd")
                else:
                    assert child.stdout is not None
                    for chunk in child.stdout:
                        if chunk:
                            emitted = True
                            yield send({"type": "text", "text": chunk})
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                stderr = ""
                if child.stderr is not None:
                    stderr = child.stderr.read()
                if stderr and re.search(r"error|denied|fatal|not found|unauthorized|forbidden|auth|login|credential|api[ -]?key|quota|rate limit|not authenticated", stderr, re.IGNORECASE):
                    saw_error = True
                    yield send({"type": "error", "msg": stderr.strip()[:200]})
                    return
                clean_exit = child.returncode == 0
                wrote_report = count_reports() > reports_before if kind == "evaluate" else True
                if not emitted and not saw_error and not clean_exit:
                    yield send({"type": "error", "msg": "The CLI exited with an error - is it installed and authenticated?"})
                elif not emitted and not saw_error:
                    yield send({"type": "error", "msg": "The CLI produced no output - is it installed and authenticated? (career-ops is best on Claude Code.)"})
                elif kind == "evaluate" and not wrote_report:
                    yield send({"type": "error", "msg": "This evaluation didn't save a report, so it's not in your tracker. Full evaluation is verified on Claude Code."})
                elif not clean_exit or saw_error:
                    yield send({"type": "error", "msg": "This run hit an error before finishing, so it isn't recorded as a confident result - re-run it to verify."})
                else:
                    yield send({"type": "done", "tokens": last_tokens, "costUsd": last_cost})
            finally:
                if child.poll() is None:
                    child.terminate()

        return StreamingHttpResponse(ndjson_stream(), content_type="text/plain; charset=utf-8", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


class ApplyCloseView(APIView):
    def post(self, request):
        session_id = str(request.data.get("sessionId") or "").strip()
        if session_id:
            close_apply_session(session_id)
        return Response({"ok": True})


class ApplySessionView(APIView):
    def post(self, request):
        url = str(request.data.get("url") or "").strip()
        if not re.match(r"^https?://", url, re.IGNORECASE):
            return Response({"error": "A valid application URL (https://...) is required"}, status=400)
        try:
            return Response(open_apply_session(url, include_screenshots=not bool(request.data.get("_noShots"))))
        except Exception as exc:
            return Response({"error": str(exc)[:200] or "could not open the form"}, status=500)


class ApplyPrefillView(APIView):
    def post(self, request):
        session_id = str(request.data.get("sessionId") or "").strip()
        cli_id = str(request.data.get("cliId") or "").strip()
        started_at = time.time()
        log_path = root_path(".career-ops-web", "apply-prefill.log")
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"\n===== django prefill {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started_at))} session={session_id} cli={cli_id} =====\n")
        except OSError:
            pass

        def events():
            def send(obj):
                return (json.dumps(obj) + "\n").encode("utf-8")

            def log(message: str):
                elapsed_ms = int((time.time() - started_at) * 1000)
                try:
                    with log_path.open("a", encoding="utf-8") as handle:
                        handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} [+{elapsed_ms / 1000:.1f}s] {message}\n")
                except OSError:
                    pass
                return send({"t": "log", "m": message, "el": elapsed_ms})

            def fail(message: str, raw: str | None = None):
                yield log(f"ERROR: {message}")
                payload = {"t": "error", "m": message}
                if raw is not None:
                    payload["raw"] = raw
                yield send(payload)

            session = get_apply_session(session_id) if session_id else None
            if session is None:
                yield from fail("apply session not found (it may have expired)")
                return

            resolved = resolve_cli(cli_id)
            if not resolved:
                yield from fail(f"CLI '{cli_id}' not found on this machine")
                return

            fields_list = "\n".join(
                f"{field.get('id', '')}\t{field.get('type', '')}{'*' if field.get('required') else ''}\t{field.get('label', '')}"
                + (f"\t[options: {' | '.join(str(option) for option in field.get('options') or [])}]" if field.get("options") else "")
                for field in session.fields
            )
            memory = read_memory().strip()
            prompt = f"""You are pre-filling a job application for the user (company/role: {session.title}). Read cv.md and config/profile.yml; if a matching report for this company exists in reports/, read it too. Ground EVERY answer in the REAL candidate - never invent facts.{f'''

Durable notes about the user:
{memory}''' if memory else ""}

FIELDS (id ⇥ type ⇥ label ⇥ options):
{fields_list}

For each field give the best answer:
- identity/contact (name, email, phone, github, linkedin, location) -> from profile/cv.
- free-text (Why us?, cover-letter, "most impactful thing you've built", etc.) -> a concise, honest, concrete answer in the candidate's own voice (no buzzwords, active voice, real metrics only). Keep each under ~120 words.
- select/radio -> choose the best-matching option using the EXACT option text from the list.
- NEVER fill legal / visa / work-authorization / salary / demographic / sensitive fields -> set needs_confirmation:true and value:"".

Output ONLY a compact JSON object mapping each field id -> {{"value": "...", "needs_confirmation": boolean}}. No prose, no markdown, no code fence."""

            yield log(f'Form: "{session.title}" · {len(session.fields)} fields · prompt {len(prompt)} chars · memory {len(memory)} chars')
            yield log(f"Planner: {cli_id} ({resolved['path']})")

            if cli_id == "claude":
                args = [
                    "-p",
                    prompt,
                    "--permission-mode",
                    "acceptEdits",
                    "--strict-mcp-config",
                    "--allowedTools",
                    "Read,Glob,Grep",
                    "--disallowedTools",
                    "Bash,Write,Edit,NotebookEdit,Task,WebFetch,WebSearch",
                ]
            else:
                args = resolved["args"](prompt)
            kill_seconds = min(300, 150 + len(session.fields) * 6)
            yield log(f"Spawning planner (timeout {kill_seconds}s)...")

            try:
                child = subprocess.Popen(
                    [resolved["path"], *args],
                    cwd=root_path(),
                    env=os.environ.copy(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                )
            except Exception as exc:
                yield from fail(f"spawn error: {exc}")
                return

            timed_out = False
            try:
                buf, stderr = child.communicate(timeout=kill_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                yield log("TIMEOUT reached -> SIGTERM")
                child.terminate()
                try:
                    buf, stderr = child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    buf, stderr = child.communicate()

            stderr = (stderr or "").strip()
            if stderr:
                yield log(f"stderr: {re.sub(r'\\s+', ' ', stderr)[:160]}")
            yield log(f"Planner exited code={child.returncode} signal={'SIGTERM' if timed_out else 'null'} · {len(buf)} chars total")
            yield log(f"output head: {re.sub(r'\\s+', ' ', buf[:100]) or '(empty)'}")
            yield log(f"output tail: {re.sub(r'\\s+', ' ', buf[-100:]) or '(empty)'}")

            if not buf.strip():
                message = "planner was killed before producing any output (try again / smaller form)" if timed_out else "planner produced no output (check the CLI works in this folder)"
                yield from fail(message)
                return

            answers, truncated = extract_json_object(buf)
            if answers is None:
                message = "planner was killed mid-answer (form too large/slow) - couldn't recover any fields" if timed_out else "couldn't parse the planner's answer as JSON"
                yield from fail(message, buf[-300:])
                return

            count = len(answers)
            yield log(f"Parsed {count} answers{' (RECOVERED from truncated output - some fields may be missing)' if truncated else ''}")
            yield send({"t": "done", "answers": answers, "truncated": truncated, "count": count})

        return StreamingHttpResponse(events(), content_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


class ApplyFillView(APIView):
    def post(self, request):
        session_id = str(request.data.get("sessionId") or "").strip()
        if not session_id:
            return Response({"error": "sessionId required"}, status=400)
        answers = request.data.get("answers") or {}
        fields = request.data.get("fields") or []
        if not isinstance(answers, dict):
            return Response({"error": "answers must be an object"}, status=400)
        if not isinstance(fields, list):
            return Response({"error": "fields must be a list"}, status=400)
        try:
            result = fill_apply_session(session_id, answers, fields)
            handed_off = bool(request.data.get("handoff"))
            if handed_off:
                handoff_apply_session(session_id)
            return Response({**result, "handedOff": handed_off, "cvAttached": False})
        except Exception as exc:
            return Response({"error": str(exc)[:200] or "fill failed"}, status=500)


class ApplyDriveView(APIView):
    def post(self, request):
        session_id = str(request.data.get("sessionId") or "").strip()
        goal = str(request.data.get("goal") or "reach").strip() or "reach"

        def events():
            def send(obj):
                return (json.dumps(obj) + "\n").encode("utf-8")

            if not session_id:
                yield send({"t": "error", "message": "sessionId required"})
                return
            try:
                result = drive_apply_session(session_id, goal)
            except Exception as exc:
                yield send({"t": "error", "message": str(exc)[:160] or "drive failed"})
                return

            for step in result.get("steps") or []:
                yield send({"t": "step", **step})
            if result.get("reached"):
                yield send(
                    {
                        "t": "done",
                        "reached": True,
                        "turns": result.get("turns", 0),
                        "title": result.get("title", "Application"),
                        "fields": result.get("fields", []),
                        "issues": result.get("issues", []),
                    }
                )
            else:
                yield send({"t": "error", "reason": result.get("reason", "stuck"), "message": result.get("reason", "Couldn't reach a fillable form on this page.")})

        return StreamingHttpResponse(events(), content_type="application/x-ndjson", headers={"Cache-Control": "no-store"})


class ExploreView(APIView):
    def post(self, request):
        if not root_path("scan-ats-full.mjs").exists():
            return Response({"error": "The discovery scanner isn't available in this checkout yet."}, status=400)
        filters = clean_explore_filters(request.data if isinstance(request.data, dict) else {})
        temp_portals = write_temp_portals(filters)
        args = [
            "scan-ats-full.mjs",
            "--dry-run",
            "--since",
            str(filters["sinceDays"]),
            "--ats",
            ",".join(filters["ats"]),
            "--limit",
            str(filters["limitPerAts"]),
        ]
        use_json = scanner_supports_json()
        if use_json:
            args.append("--json")

        def events():
            encoder = lambda obj: (json.dumps(obj) + "\n").encode("utf-8")
            yield encoder({"kind": "start", "ats": filters["ats"], "sinceDays": filters["sinceDays"], "limit": filters["limitPerAts"], "free": True})
            env = {**os.environ, "CAREER_OPS_PORTALS": temp_portals}
            try:
                child = subprocess.run(["node", *args], cwd=root_path(), env=env, text=True, capture_output=True, timeout=230, check=False)
                for line in (child.stderr or "").splitlines():
                    if line.strip():
                        yield encoder({"kind": "log", "line": line.strip()})
                offers = []
                if use_json:
                    try:
                        data = json.loads((child.stdout or "").strip() or "{}")
                    except json.JSONDecodeError:
                        data = {}
                    for raw in data.get("offers") or []:
                        if not raw.get("url") or not raw.get("company") or not raw.get("title"):
                            continue
                        source = raw.get("source") or "scan"
                        offer = {
                            "url": raw.get("url"),
                            "company": raw.get("company"),
                            "title": raw.get("title"),
                            "location": raw.get("location") or "",
                            "postedAt": raw.get("postedAt") or "",
                            "ats": str(source).replace("-full", ""),
                            "source": source,
                        }
                        offers.append(offer)
                        yield encoder({"kind": "offer", "offer": offer})
                    yield encoder(
                        {
                            "kind": "summary",
                            "companiesScanned": data.get("companiesScanned", 0),
                            "unreachable": data.get("unreachableBoards", 0),
                            "matches": data.get("postingsKept", len(offers)),
                            "companiesAvailable": data.get("companiesAvailable"),
                            "capHit": data.get("capHit"),
                            "datasetStatus": data.get("datasetStatus"),
                            "postingsDroppedNoDate": data.get("postingsDroppedNoDate"),
                        }
                    )
                else:
                    yield encoder({"kind": "log", "line": "Legacy scanner output is not parsed by Django yet; use Next fallback for detailed progress."})
                if child.returncode != 0:
                    yield encoder({"kind": "error", "message": (child.stderr or child.stdout or "discovery failed").strip().splitlines()[-1]})
                yield encoder({"kind": "done", "count": len(offers), "offers": offers, "cost": {"tokens": 0, "usd": 0}})
            except Exception as exc:
                yield encoder({"kind": "error", "message": str(exc) or "discovery failed"})
                yield encoder({"kind": "done", "count": 0, "offers": [], "cost": {"tokens": 0, "usd": 0}})
            finally:
                try:
                    Path(temp_portals).unlink(missing_ok=True)
                except OSError:
                    pass

        return StreamingHttpResponse(events(), content_type="application/x-ndjson; charset=utf-8", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
