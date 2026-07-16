from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import time

import pytest
from django.test import override_settings


@pytest.fixture()
def career_root(tmp_path: Path) -> Path:
    (tmp_path / "data").mkdir()
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "states.yml").write_text(
        """
states:
  - id: evaluated
    label: Evaluated
    aliases: []
  - id: applied
    label: Applied
    aliases: [sent]
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "tracker-aliases.json").write_text(
        '{"#":"num","date":"date","company":"company","role":"role","score":"score","status":"status","pdf":"pdf","report":"report","notes":"notes"}',
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.django_db
def test_pipeline_reads_file_backed_state(client, career_root):
    (career_root / "data" / "pipeline.md").write_text(
        "- [ ] https://example.test/job | Acme | Staff Engineer | Remote | EUR 100k\n",
        encoding="utf-8",
    )
    (career_root / "data" / "applications.md").write_text(
        "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        "| 1 | 2026-07-14 | Acme | Staff Engineer | 4.1/5 | Evaluated | - | [1](reports/001-acme.md) | Fit |\n",
        encoding="utf-8",
    )

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/pipeline")

    assert response.status_code == 200
    body = response.json()
    assert body["inbox"][0]["company"] == "Acme"
    assert body["applications"][0]["status"] == "Evaluated"


def test_cv_get_missing_is_empty(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/cv")

    assert response.status_code == 200
    assert response.json() == {"content": "", "exists": False}


def test_cv_pdf_serves_newest_matching_company_pdf(client, career_root):
    output = career_root / "output"
    output.mkdir()
    old_pdf = output / "cv-user-acme-2026-01-01.pdf"
    new_pdf = output / "cv-user-acme-2026-07-14.pdf"
    old_pdf.write_bytes(b"%PDF-old")
    new_pdf.write_bytes(b"%PDF-new")
    old_time = 1_700_000_000
    new_time = 1_800_000_000
    import os

    os.utime(old_pdf, (old_time, old_time))
    os.utime(new_pdf, (new_time, new_time))

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/cv-pdf?company=Acme")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'inline; filename="cv-user-acme-2026-07-14.pdf"'
    assert b"".join(response.streaming_content) == b"%PDF-new"


def test_cv_pdf_404_when_missing(client, career_root):
    (career_root / "output").mkdir()

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/cv-pdf?company=Acme")

    assert response.status_code == 404
    assert response.content == b"no tailored CV found for this offer"


def test_status_updates_existing_row_only(client, career_root):
    tracker = career_root / "data" / "applications.md"
    tracker.write_text(
        "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        "| 1 | 2026-07-14 | Acme | Staff Engineer | 4.1/5 | Evaluated | - | [1](reports/001-acme.md) | Fit |\n",
        encoding="utf-8",
    )

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/status", {"n": "1", "status": "sent"}, content_type="application/json")

    assert response.status_code == 200
    assert response.json()["status"] == "Applied"
    assert "| 1 | 2026-07-14 | Acme | Staff Engineer | 4.1/5 | Applied |" in tracker.read_text(encoding="utf-8")


def test_tracker_delete_dry_run_does_not_modify_tracker(client, career_root):
    tracker = career_root / "data" / "applications.md"
    original = (
        "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        "| 1 | 2026-07-14 | Acme | Staff Engineer | 4.1/5 | Evaluated | - | [1](reports/001-acme.md) | Fit |\n"
    )
    tracker.write_text(original, encoding="utf-8")
    (career_root / "tracker.mjs").write_text(
        "#!/usr/bin/env node\n"
        "if (process.argv.includes('--dry-run')) {\n"
        "  console.error('Would remove application 1 (1 row) from data/applications.md.');\n"
        "  console.error('(report file would be orphaned: [1](reports/001-acme.md))');\n"
        "  process.exit(0);\n"
        "}\n"
        "process.exit(1);\n",
        encoding="utf-8",
    )

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/tracker/delete", {"n": "1", "dryRun": True}, content_type="application/json")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "dryRun": True, "orphanReport": "[1](reports/001-acme.md)"}
    assert tracker.read_text(encoding="utf-8") == original


def test_version_matches_web_contract(client, career_root):
    (career_root / "VERSION").write_text("1.2.3-rc.1 # comment\n", encoding="utf-8")
    (career_root / "web").mkdir()
    (career_root / "web" / "package.json").write_text('{"version":"0.3.0"}', encoding="utf-8")

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/version")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "web 0.3.0"
    assert body["coreVersion"] == "1.2.3-rc.1"
    assert body["channel"] == "rc"
    assert "sha" in body


def test_followups_wraps_core_script(client, career_root):
    (career_root / "followup-cadence.mjs").write_text(
        "#!/usr/bin/env node\n"
        "console.log(JSON.stringify({metadata:{overdue:1},entries:["
        "{company:'UrgentCo',role:'AI Engineer',urgency:'overdue'},"
        "{company:'WaitCo',role:'PM',urgency:'waiting'}"
        "]}));\n",
        encoding="utf-8",
    )

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/followups")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["metadata"] == {"overdue": 1}
    assert body["entries"][0]["company"] == "UrgentCo"


def test_usage_reads_claude_jsonl(client, tmp_path, monkeypatch):
    projects = tmp_path / "claude-projects" / "proj"
    projects.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    events = [
        {
            "timestamp": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "message": {"usage": {"input_tokens": 10, "output_tokens": 5, "cache_creation_input_tokens": 2}},
        },
        {
            "timestamp": (now - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            "message": {"usage": {"input_tokens": 20, "output_tokens": 1}},
        },
    ]
    (projects / "session.jsonl").write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    monkeypatch.setenv("CAREER_OPS_CLAUDE_PROJECTS_DIR", str(tmp_path / "claude-projects"))

    response = client.get("/api/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["window5h"] == {"tokens": 17, "messages": 1}
    assert body["window7d"] == {"tokens": 38, "messages": 2}
    assert isinstance(body["computedAt"], int)


def test_report_shape_counts_structure_only(client, career_root):
    (career_root / "data" / "pipeline.md").write_text("- [ ] https://example.test | Acme | Engineer\n", encoding="utf-8")
    (career_root / "data" / "applications.md").write_text(
        "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        "| 1 | 2026-07-14 | Acme | Engineer | 4.0/5 | Applied | - | - | Applied 2026-07-14 |\n",
        encoding="utf-8",
    )
    (career_root / "reports").mkdir()
    (career_root / "reports" / "001-acme.md").write_text("# report", encoding="utf-8")
    (career_root / "output").mkdir()
    (career_root / "output" / "cv.pdf").write_bytes(b"%PDF")

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/report/shape")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["inbox"] == {"candidates": 1, "parsed": 1}
    assert body["data"]["tracker"] == {"candidates": 1, "parsed": 1}
    assert body["data"]["reports"] == 1
    assert body["data"]["pdfs"] == 1


def test_memory_reads_and_appends_managed_profile_block(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        post = client.post("/api/memory", {"fact": "Prefers remote AI platform roles"}, content_type="application/json")
        get = client.get("/api/memory")

    assert post.status_code == 200
    assert post.json() == {"ok": True, "deduped": False}
    assert "Prefers remote AI platform roles" in get.json()["memory"]
    profile = career_root / "modes" / "_profile.md"
    assert "<!-- co-web-notes:start -->" in profile.read_text(encoding="utf-8")


def test_followups_log_appends_line(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post(
            "/api/followups/log",
            {"num": 7, "company": "Acme", "note": "Sent concise follow-up"},
            content_type="application/json",
        )

    assert response.status_code == 200
    content = (career_root / "data" / "follow-ups.md").read_text(encoding="utf-8")
    assert "#7 Acme" in content
    assert "Sent concise follow-up" in content


def test_explore_known_collects_seen_urls(client, career_root):
    (career_root / "data" / "scan-history.tsv").write_text("url\tfirst_seen\nhttps://example.test/job/\t2026-07-14\n", encoding="utf-8")
    (career_root / "data" / "pipeline.md").write_text("- [ ] https://example.test/other | Acme | Engineer\n", encoding="utf-8")

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.get("/api/explore/ai/known")

    assert response.status_code == 200
    assert response.json()["urls"] == ["https://example.test/job", "https://example.test/other"]


def test_explore_missing_scanner_fails_soft(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/explore", {}, content_type="application/json")

    assert response.status_code == 400
    assert "scanner" in response.json()["error"]


def test_explore_ai_requires_query_and_cli(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/explore/ai", {}, content_type="application/json")

    assert response.status_code == 400
    assert response.json() == {"error": "query and cliId required"}


def test_explore_ai_reports_missing_cli(client, career_root, monkeypatch):
    monkeypatch.setenv("PATH", str(career_root / "empty-bin"))

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/explore/ai", {"query": "ai roles", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 404
    assert response.json() == {"error": "CLI 'codex' not found on this machine"}


def test_explore_ai_reports_missing_mode_after_cli_resolution(client, career_root, monkeypatch):
    bindir = career_root / "bin"
    bindir.mkdir()
    codex = bindir / "codex"
    codex.write_text("#!/bin/sh\necho should-not-run\n", encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/explore/ai", {"query": "ai roles", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 400
    assert response.json()["code"] == "MODE_MISSING"


def test_explore_ai_streams_text_from_cli(client, career_root, monkeypatch):
    bindir = career_root / "bin"
    bindir.mkdir()
    codex = bindir / "codex"
    codex.write_text("#!/bin/sh\necho streamed-offer\n", encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    (career_root / "modes").mkdir()
    (career_root / "modes" / "discover.md").write_text("# Discover mode\n", encoding="utf-8")

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/explore/ai", {"query": "ai roles", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert b"streamed-offer" in b"".join(response.streaming_content)


def test_run_requires_input_and_cli(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/run", {}, content_type="application/json")

    assert response.status_code == 400
    assert response.json() == {"error": "input and cliId required"}


def test_run_reports_missing_cli(client, career_root, monkeypatch):
    monkeypatch.setenv("PATH", str(career_root / "empty-bin"))

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/run", {"kind": "research", "input": "https://example.test", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 404
    assert response.json() == {"error": "CLI 'codex' not found"}


def test_run_evaluate_requires_complete_checkout_before_cv(client, career_root, monkeypatch):
    bindir = career_root / "bin"
    bindir.mkdir()
    codex = bindir / "codex"
    codex.write_text("#!/bin/sh\necho should-not-run\n", encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/run", {"kind": "evaluate", "input": "https://example.test", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 400
    assert "modes/oferta.md" in response.json()["error"]


def test_run_evaluate_requires_cv_after_mode_exists(client, career_root, monkeypatch):
    bindir = career_root / "bin"
    bindir.mkdir()
    codex = bindir / "codex"
    codex.write_text("#!/bin/sh\necho should-not-run\n", encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    (career_root / "modes").mkdir()
    (career_root / "modes" / "oferta.md").write_text("# oferta\n", encoding="utf-8")

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/run", {"kind": "evaluate", "input": "https://example.test", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 400
    assert "Add your CV first" in response.json()["error"]


def test_run_research_streams_ndjson_from_cli(client, career_root, monkeypatch):
    bindir = career_root / "bin"
    bindir.mkdir()
    codex = bindir / "codex"
    codex.write_text("#!/bin/sh\necho 'Research text'\necho 'VERDICT: 4/5 - useful signal'\n", encoding="utf-8")
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))

    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/run", {"kind": "research", "input": "https://example.test", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 200
    payload = b"".join(response.streaming_content).decode("utf-8")
    assert '"type": "text"' in payload
    assert "VERDICT: 4/5" in payload
    assert '"type": "done"' in payload


def test_apply_close_is_idempotent_contract(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/apply/close", {"sessionId": "missing"}, content_type="application/json")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_apply_session_rejects_bad_json(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/apply/session", data="{", content_type="application/json")

    assert response.status_code == 400


def test_apply_session_rejects_invalid_url(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/apply/session", {"url": "not-a-url"}, content_type="application/json")

    assert response.status_code == 400
    assert response.json() == {"error": "A valid application URL (https://...) is required"}


def test_apply_prefill_contract_streams_missing_session_error(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/apply/prefill", {"sessionId": "missing", "cliId": "codex"}, content_type="application/json")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/x-ndjson")
    payload = b"".join(response.streaming_content).decode("utf-8")
    assert '"t": "log"' in payload
    assert '"t": "error"' in payload
    assert "apply session not found" in payload


def test_apply_prefill_streams_answers_for_django_session(client, career_root, monkeypatch):
    from apps.core.apply_sessions import ApplySession, SESSIONS

    bindir = career_root / "bin"
    bindir.mkdir()
    codex = bindir / "codex"
    codex.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' '{\"first_name\":{\"value\":\"Ada\",\"needs_confirmation\":false}}'\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir))
    (career_root / "cv.md").write_text("# CV\n\nAda Lovelace", encoding="utf-8")
    (career_root / "config").mkdir()
    (career_root / "config" / "profile.yml").write_text("name: Ada Lovelace\n", encoding="utf-8")

    SESSIONS["apply-test"] = ApplySession(
        id="apply-test",
        url="https://example.test/apply",
        title="Example Application",
        fields=[{"id": "first_name", "type": "text", "label": "First name", "required": True}],
        context=None,
        page=None,
        created_at=time.time(),
    )
    try:
        with override_settings(CAREER_OPS_ROOT=career_root):
            response = client.post("/api/apply/prefill", {"sessionId": "apply-test", "cliId": "codex"}, content_type="application/json")

        assert response.status_code == 200
        payload = b"".join(response.streaming_content).decode("utf-8")
        assert '"t": "done"' in payload
        assert '"first_name"' in payload
        assert '"count": 1' in payload
    finally:
        SESSIONS.pop("apply-test", None)


class FakeLocator:
    def __init__(self, calls):
        self.calls = calls

    def first(self):
        return self

    def fill(self, value):
        self.calls.append(("fill", value))

    def select_option(self, **kwargs):
        self.calls.append(("select_option", kwargs))

    def set_checked(self, value):
        self.calls.append(("set_checked", value))

    def check(self):
        self.calls.append(("check", None))


class FakeApplyPage:
    url = "https://example.test/apply"

    def __init__(self):
        self.calls = []

    def locator(self, selector):
        self.calls.append(("locator", selector))
        return FakeLocator(self.calls)

    def bring_to_front(self):
        self.calls.append(("bring_to_front", None))


class FakeDriveLocator:
    def __init__(self, page, exists=True, label="Apply", attr_type="button"):
        self.page = page
        self.exists = exists
        self.label = label
        self.attr_type = attr_type

    def first(self):
        return self

    def count(self):
        return 1 if self.exists else 0

    def click(self, timeout=None):
        self.page.calls.append(("drive_click", self.label))
        self.page.fields = [{"id": "email", "nativeId": "email", "type": "email", "label": "Email", "required": True}]

    def get_attribute(self, name):
        return self.attr_type if name == "type" else None

    def inner_text(self, timeout=None):
        return self.label


class FakeDrivePage:
    url = "https://example.test/job"

    def __init__(self, fields=None, click_exists=True):
        self.fields = fields or []
        self.click_exists = click_exists
        self.calls = []

    def evaluate(self, script):
        return self.fields

    def title(self):
        return "Example Application"

    def get_by_role(self, role, name):
        exists = self.click_exists and role == "button"
        return FakeDriveLocator(self, exists=exists, label="Apply")

    def wait_for_load_state(self, *args, **kwargs):
        self.calls.append(("wait_for_load_state", None))

    def wait_for_timeout(self, *args, **kwargs):
        self.calls.append(("wait_for_timeout", None))


class FakeFormContext:
    def __init__(self, fields):
        self.fields = fields

    def evaluate(self, script):
        return self.fields

    def locator(self, selector):
        return FakeLocator([])


class FakeFramesPage:
    url = "https://example.test/job"

    def __init__(self, frames):
        self.frames = frames

    def evaluate(self, script):
        return []

    def screenshot(self, **kwargs):
        return b"fake-jpeg"


def test_apply_session_pick_form_context_prefers_application_iframe():
    from apps.core.apply_sessions import pick_form_context

    listing = FakeFormContext([{"id": "q", "type": "text", "label": "Search jobs"}, {"id": "loc", "type": "text", "label": "Location"}])
    application = FakeFormContext([{"id": "email", "type": "email", "label": "Email"}, {"id": "resume", "type": "file", "label": "Resume/CV"}])
    fields, frame, issues = pick_form_context(FakeFramesPage([listing, application]))

    assert frame is application
    assert [field["id"] for field in fields] == ["email", "resume"]
    assert issues == []


def test_apply_session_pick_form_context_filters_listing_search_fields():
    from apps.core.apply_sessions import pick_form_context

    listing = FakeFormContext([{"id": "keyword", "type": "text", "label": "Keyword search"}, {"id": "department", "type": "select", "label": "Department"}])
    fields, frame, issues = pick_form_context(FakeFramesPage([listing]))

    assert frame is listing
    assert fields == []
    assert issues[0]["code"] == "listing-or-search-form"


def test_apply_session_diagnostics_and_shots_are_best_effort():
    from apps.core.apply_sessions import apply_session_diagnostics, capture_apply_shots, pick_form_context

    application = FakeFormContext([{"id": "email", "type": "email", "label": "Email"}])
    page = FakeFramesPage([application])
    fields, _frame, issues = pick_form_context(page)
    diagnostics = apply_session_diagnostics(page, fields, issues)
    shots = capture_apply_shots(page)

    assert diagnostics == {"frames": 1, "fields": 1, "classification": "application", "issueCodes": []}
    assert len(shots) == 1
    assert shots[0].startswith("data:image/jpeg;base64,")


def test_apply_fill_rejects_missing_session_id(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/apply/fill", {"answers": {}}, content_type="application/json")

    assert response.status_code == 400
    assert response.json() == {"error": "sessionId required"}


def test_apply_fill_fills_django_session_without_submit(client, career_root):
    from apps.core.apply_sessions import ApplySession, SESSIONS

    page = FakeApplyPage()
    SESSIONS["apply-fill-test"] = ApplySession(
        id="apply-fill-test",
        url="https://example.test/apply",
        title="Example Application",
        fields=[
            {"id": "first_name", "nativeId": "first_name", "type": "text", "label": "First name"},
            {"id": "country", "nativeName": "country", "type": "select", "label": "Country"},
        ],
        context=None,
        page=page,
        created_at=time.time(),
    )
    try:
        with override_settings(CAREER_OPS_ROOT=career_root):
            response = client.post(
                "/api/apply/fill",
                {
                    "sessionId": "apply-fill-test",
                    "answers": {"first_name": "Ada", "country": "France"},
                    "fields": [
                        {"id": "first_name", "nativeId": "first_name", "type": "text", "label": "First name"},
                        {"id": "country", "nativeName": "country", "type": "select", "label": "Country"},
                    ],
                },
                content_type="application/json",
            )

        assert response.status_code == 200
        body = response.json()
        assert body["navigated"] is False
        assert body["handedOff"] is False
        assert body["cvAttached"] is False
        assert [step["ok"] for step in body["steps"]] == [True, True]
        assert ("fill", "Ada") in page.calls
        assert ("select_option", {"label": "France"}) in page.calls
    finally:
        SESSIONS.pop("apply-fill-test", None)


def test_apply_fill_does_not_tick_consent_checkbox(client, career_root):
    from apps.core.apply_sessions import ApplySession, SESSIONS

    page = FakeApplyPage()
    SESSIONS["apply-consent-test"] = ApplySession(
        id="apply-consent-test",
        url="https://example.test/apply",
        title="Example Application",
        fields=[{"id": "terms", "nativeId": "terms", "type": "checkbox", "label": "I agree to the terms"}],
        context=None,
        page=page,
        created_at=time.time(),
    )
    try:
        with override_settings(CAREER_OPS_ROOT=career_root):
            response = client.post(
                "/api/apply/fill",
                {"sessionId": "apply-consent-test", "answers": {"terms": "true"}},
                content_type="application/json",
            )

        assert response.status_code == 200
        body = response.json()
        assert body["steps"] == [{"fieldId": "terms", "label": "I agree to the terms - you confirm", "ok": False}]
        assert ("set_checked", True) not in page.calls
    finally:
        SESSIONS.pop("apply-consent-test", None)


def test_apply_drive_streams_missing_session_error(client, career_root):
    with override_settings(CAREER_OPS_ROOT=career_root):
        response = client.post("/api/apply/drive", {"sessionId": "missing"}, content_type="application/json")

    assert response.status_code == 200
    payload = b"".join(response.streaming_content).decode("utf-8")
    assert '"t": "error"' in payload
    assert "apply session not found" in payload


def test_apply_drive_refuses_full_mode_for_django_session(client, career_root):
    from apps.core.apply_sessions import ApplySession, SESSIONS

    SESSIONS["apply-drive-full"] = ApplySession(
        id="apply-drive-full",
        url="https://example.test/job",
        title="Example",
        fields=[],
        context=None,
        page=FakeDrivePage(),
        created_at=time.time(),
    )
    try:
        with override_settings(CAREER_OPS_ROOT=career_root):
            response = client.post("/api/apply/drive", {"sessionId": "apply-drive-full", "goal": "full"}, content_type="application/json")

        payload = b"".join(response.streaming_content).decode("utf-8")
        assert '"t": "error"' in payload
        assert "only supports reach mode" in payload
    finally:
        SESSIONS.pop("apply-drive-full", None)


def test_apply_drive_returns_done_when_form_already_reached(client, career_root):
    from apps.core.apply_sessions import ApplySession, SESSIONS

    page = FakeDrivePage(fields=[{"id": "email", "nativeId": "email", "type": "email", "label": "Email"}])
    SESSIONS["apply-drive-ready"] = ApplySession(
        id="apply-drive-ready",
        url="https://example.test/apply",
        title="Example",
        fields=[],
        context=None,
        page=page,
        created_at=time.time(),
    )
    try:
        with override_settings(CAREER_OPS_ROOT=career_root):
            response = client.post("/api/apply/drive", {"sessionId": "apply-drive-ready"}, content_type="application/json")

        payload = b"".join(response.streaming_content).decode("utf-8")
        assert '"t": "done"' in payload
        assert '"reached": true' in payload
        assert '"email"' in payload
        assert page.calls == []
    finally:
        SESSIONS.pop("apply-drive-ready", None)


def test_apply_drive_clicks_safe_apply_and_extracts_fields(client, career_root):
    from apps.core.apply_sessions import ApplySession, SESSIONS

    page = FakeDrivePage()
    SESSIONS["apply-drive-click"] = ApplySession(
        id="apply-drive-click",
        url="https://example.test/job",
        title="Example",
        fields=[],
        context=None,
        page=page,
        created_at=time.time(),
    )
    try:
        with override_settings(CAREER_OPS_ROOT=career_root):
            response = client.post("/api/apply/drive", {"sessionId": "apply-drive-click"}, content_type="application/json")

        payload = b"".join(response.streaming_content).decode("utf-8")
        assert '"t": "step"' in payload
        assert '"t": "done"' in payload
        assert ("drive_click", "Apply") in page.calls
    finally:
        SESSIONS.pop("apply-drive-click", None)
