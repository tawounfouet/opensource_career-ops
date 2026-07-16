from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class ApplySession:
    id: str
    url: str
    title: str
    fields: list[dict[str, Any]]
    context: Any
    page: Any
    created_at: float
    frame: Any = None


SESSIONS: dict[str, ApplySession] = {}
PLAYWRIGHT = None
BROWSER = None


def prune_sessions(max_age_seconds: int = 15 * 60) -> None:
    now = time.time()
    for session_id, session in list(SESSIONS.items()):
        if now - session.created_at > max_age_seconds:
            close_apply_session(session_id)


def close_apply_session(session_id: str) -> None:
    session = SESSIONS.pop(session_id, None)
    if session:
        try:
            session.context.close()
        except Exception:
            pass


def get_apply_session(session_id: str) -> ApplySession | None:
    return SESSIONS.get(session_id)


def browser():
    global PLAYWRIGHT, BROWSER
    if BROWSER is not None and BROWSER.is_connected():
        return BROWSER
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("Python Playwright is not installed. Run: pip install -e 'backend[dev]'") from exc
    if PLAYWRIGHT is None:
        PLAYWRIGHT = sync_playwright().start()
    headless = os.environ.get("CAREER_OPS_APPLY_HEADLESS", "0").lower() in {"1", "true", "yes"}
    launch_args = ["--window-position=-3200,-3200", "--window-size=1280,940"]
    try:
        BROWSER = PLAYWRIGHT.chromium.launch(channel="chrome", headless=headless, args=launch_args)
    except Exception:
        BROWSER = PLAYWRIGHT.chromium.launch(headless=headless, args=launch_args)
    return BROWSER


def extract_fields_from_context(context) -> list[dict[str, Any]]:
    return context.evaluate(
        """
() => Array.from(document.querySelectorAll('input, textarea, select')).map((el, i) => {
  const id = el.id || el.name || `field-${i}`;
  const labelEl = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
  const wrapLabel = el.closest('label');
  const label = (labelEl?.innerText || wrapLabel?.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.name || el.id || id || '').trim();
  const tag = el.tagName.toLowerCase();
  const type = tag === 'textarea' ? 'textarea' : tag === 'select' ? 'select' : (el.getAttribute('type') || 'text').toLowerCase();
  const options = tag === 'select' ? Array.from(el.options).map(o => o.textContent.trim()).filter(Boolean) : undefined;
  return {
    id,
    label,
    type,
    required: !!el.required,
    nativeId: el.id || '',
    nativeName: el.name || '',
    options,
  };
}).filter(f => f.type !== 'hidden')
"""
    )


def _page_contexts(page) -> list[Any]:
    contexts: list[Any] = []
    try:
        frames = page.frames
        if callable(frames):
            frames = frames()
        contexts.extend(frames or [])
    except Exception:
        pass
    if not contexts:
        contexts.append(page)
    return contexts


def extract_fields(page) -> list[dict[str, Any]]:
    fields, _frame, _issues = pick_form_context(page)
    return fields


def looks_like_application_fields(fields: list[dict[str, Any]]) -> bool:
    if not fields:
        return False
    labels = " ".join(str(field.get("label") or "") for field in fields).lower()
    types = {str(field.get("type") or "").lower() for field in fields}
    return bool(
        "file" in types
        or "email" in types
        or re.search(r"first name|last name|full name|resume|résumé|\bcv\b|cover letter|phone|linkedin|github|portfolio|sponsorship|relocat", labels)
    )


def looks_like_search_or_listing_fields(fields: list[dict[str, Any]]) -> bool:
    if not fields:
        return False
    labels = " ".join(str(field.get("label") or "") for field in fields).lower()
    if looks_like_application_fields(fields):
        return False
    searchish = re.search(r"search|keyword|filter|department|office|location|remote|category|job alert|query", labels)
    return bool(searchish and len(fields) <= 6)


def _field_score(fields: list[dict[str, Any]]) -> int:
    score = len(fields)
    if looks_like_application_fields(fields):
        score += 100
    if looks_like_search_or_listing_fields(fields):
        score -= 50
    return score


def pick_form_context(page) -> tuple[list[dict[str, Any]], Any, list[dict[str, str]]]:
    best_fields: list[dict[str, Any]] = []
    best_context = page
    best_score = -10_000
    for context in _page_contexts(page):
        try:
            fields = extract_fields_from_context(context)
        except Exception:
            continue
        score = _field_score(fields)
        if score > best_score:
            best_fields = fields
            best_context = context
            best_score = score

    if looks_like_application_fields(best_fields):
        return best_fields, best_context, []
    if looks_like_search_or_listing_fields(best_fields):
        return [], best_context, [
            {
                "level": "info",
                "code": "listing-or-search-form",
                "message": "Django saw only listing/search fields, not a job application form. Use drive/reach or paste the direct Apply URL.",
            }
        ]
    if best_fields:
        return [], best_context, [
            {
                "level": "warn",
                "code": "not-application-form",
                "message": "Django found fields but they do not look like a real application form yet.",
            }
        ]
    return [], best_context, []


def apply_session_diagnostics(page, fields: list[dict[str, Any]], issues: list[dict[str, str]]) -> dict[str, Any]:
    contexts = _page_contexts(page)
    return {
        "frames": len(contexts),
        "fields": len(fields),
        "classification": "application" if looks_like_application_fields(fields) else "listing-search" if issues and issues[0].get("code") == "listing-or-search-form" else "unknown",
        "issueCodes": [issue.get("code", "") for issue in issues],
    }


def capture_apply_shots(page, enabled: bool = True) -> list[str]:
    if not enabled:
        return []
    try:
        shot = page.screenshot(type="jpeg", quality=42)
        if isinstance(shot, str):
            shot_bytes = shot.encode("utf-8")
        else:
            shot_bytes = bytes(shot)
        import base64

        return [f"data:image/jpeg;base64,{base64.b64encode(shot_bytes).decode('ascii')}"]
    except Exception:
        return []


def _safe_apply_button_texts() -> list[str]:
    return ["apply", "apply now", "postuler", "candidater", "start application", "begin application"]


def try_apply_trigger(page) -> tuple[bool, str]:
    candidates = _safe_apply_button_texts()
    for text in candidates:
        try:
            locator = page.get_by_role("link", name=re.compile(rf"^\s*{re.escape(text)}\s*$", re.IGNORECASE)).first()
            if locator.count() > 0:
                locator.click(timeout=5000)
                return True, f'click link "{text}"'
        except Exception:
            pass
        try:
            locator = page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(text)}\s*$", re.IGNORECASE)).first()
            if locator.count() > 0:
                button_type = (locator.get_attribute("type") or "").lower()
                label = (locator.inner_text(timeout=1000) or text).strip()
                if button_type == "submit" or re.search(r"\b(submit|send application|finish|complete application)\b", label, re.IGNORECASE):
                    return False, f'blocked submit "{label[:40]}"'
                locator.click(timeout=5000)
                return True, f'click button "{label[:40] or text}"'
        except Exception:
            pass
    return False, "no safe apply trigger found"


def drive_apply_session(session_id: str, goal: str = "reach") -> dict[str, Any]:
    session = get_apply_session(session_id)
    if session is None:
        raise RuntimeError("apply session not found (it may have expired)")
    if goal != "reach":
        raise RuntimeError("Django apply/drive only supports reach mode; full fill remains disabled to prevent automated submission")

    steps: list[dict[str, Any]] = []
    fields, frame, _issues = pick_form_context(session.page)
    if looks_like_application_fields(fields):
        session.fields = fields
        session.frame = frame
        return {
            "reached": True,
            "turns": 0,
            "title": session.page.title() or session.title,
            "fields": fields,
            "issues": [{"level": "info", "code": "django-drive", "message": "Django detected a fillable application form without agentic actions."}],
            "steps": steps,
        }

    clicked, detail = try_apply_trigger(session.page)
    steps.append({"turn": 1, "action": "click" if clicked else "stuck", "detail": detail})
    if clicked:
        try:
            session.page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            session.page.wait_for_timeout(800)
        except Exception:
            pass
        fields, frame, _issues = pick_form_context(session.page)
        if looks_like_application_fields(fields):
            session.fields = fields
            session.frame = frame
            session.title = session.page.title() or session.title
            return {
                "reached": True,
                "turns": 1,
                "title": session.title,
                "fields": fields,
                "issues": [{"level": "info", "code": "django-drive", "message": "Django reached the application form via a safe non-submit Apply trigger."}],
                "steps": steps,
            }

    return {"reached": False, "turns": len(steps), "reason": detail, "steps": steps}


def open_apply_session(url: str, include_screenshots: bool = True) -> dict[str, Any]:
    prune_sessions()
    b = browser()
    context = b.new_context(viewport={"width": 1280, "height": 900})
    context.set_default_timeout(8000)
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        try:
            page.wait_for_load_state("load", timeout=8_000)
        except Exception:
            pass
        title = page.title() or "Application"
        fields, frame, issues = pick_form_context(page)
        shots = capture_apply_shots(page, include_screenshots)
        diagnostics = apply_session_diagnostics(page, fields, issues)
        session_id = f"apply-{uuid.uuid4()}"
        SESSIONS[session_id] = ApplySession(
            id=session_id,
            url=url,
            title=title,
            fields=fields,
            context=context,
            page=page,
            created_at=time.time(),
            frame=frame,
        )
        response: dict[str, Any] = {"id": session_id, "title": title, "fields": fields, "shots": shots, "issues": issues, "diagnostics": diagnostics}
        if issues and not fields:
            response["needsDrive"] = True
        return response
    except Exception:
        try:
            context.close()
        except Exception:
            pass
        raise


def _field_selector(field: dict[str, Any]) -> str:
    native_id = str(field.get("nativeId") or "")
    native_name = str(field.get("nativeName") or "")
    field_id = str(field.get("id") or "")
    if native_id:
        return f'[id="{_css_attr(native_id)}"]'
    if native_name:
        return f'[name="{_css_attr(native_name)}"]'
    return f'[id="{_css_attr(field_id)}"]'


def _css_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _is_consent_checkbox(field: dict[str, Any]) -> bool:
    label = str(field.get("label") or "")
    return bool(
        field.get("type") == "checkbox"
        and re.search(
            r"\b(i (have )?read|i agree|i consent|i accept|consent to|privacy notice|terms|gdpr|data protection)\b",
            label,
            re.IGNORECASE,
        )
    )


def _page_path(page) -> str:
    try:
        from urllib.parse import urlparse

        return urlparse(page.url).path
    except Exception:
        try:
            return page.url
        except Exception:
            return ""


def fill_apply_session(
    session_id: str,
    answers: dict[str, Any],
    fields_meta: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    session = get_apply_session(session_id)
    if session is None:
        raise RuntimeError("apply session not found (it may have expired)")

    fields = fields_meta or session.fields
    by_id = {str(field.get("id")): field for field in fields if field.get("id") is not None}
    steps: list[dict[str, Any]] = []
    start_path = _page_path(session.page)

    for field_id, raw_value in (answers or {}).items():
        field = by_id.get(str(field_id))
        value = "" if raw_value is None else str(raw_value)
        if not field or value == "":
            continue

        field_type = str(field.get("type") or "text").lower()
        label = str(field.get("label") or field_id)
        if field_type == "file":
            steps.append({"fieldId": field_id, "label": f"{label} - left for user", "ok": False})
            continue
        if _is_consent_checkbox(field):
            steps.append({"fieldId": field_id, "label": f"{label} - you confirm", "ok": False})
            continue

        ok = False
        try:
            target = session.frame or session.page
            locator = target.locator(_field_selector(field)).first()
            if field_type == "select":
                try:
                    locator.select_option(label=value)
                except Exception:
                    locator.select_option(value=value)
            elif field_type == "checkbox":
                want = value.lower() in {"true", "1", "yes", "on", "checked"}
                locator.set_checked(want)
            elif field_type == "radio":
                selector = _field_selector(field)
                try:
                    target.locator(f'{selector}[value="{_css_attr(value)}"]').first().check()
                except Exception:
                    locator.check()
            else:
                locator.fill(value)
            ok = True
        except Exception:
            ok = False
        steps.append({"fieldId": field_id, "label": label, "ok": ok})

    end_path = _page_path(session.page)
    return {"steps": steps, "navigated": end_path != start_path, "issues": []}


def handoff_apply_session(session_id: str) -> None:
    session = get_apply_session(session_id)
    if session is None:
        raise RuntimeError("apply session not found")
    try:
        session.page.bring_to_front()
    except Exception:
        pass
