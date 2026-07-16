from pathlib import Path

import pytest


def playwright_page():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        pytest.skip("Python Playwright is not installed")

    manager = sync_playwright().start()
    try:
        browser = None
        try:
            browser = manager.chromium.launch(channel="chrome", headless=True)
        except Exception:
            try:
                browser = manager.chromium.launch(headless=True)
            except Exception:
                pytest.skip("Chromium/Chrome is not installed for Playwright")
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        yield page
        context.close()
        browser.close()
    finally:
        manager.stop()


def fixture_url(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / "apply" / name).resolve().as_uri()


def test_apply_session_extracts_direct_form_fixture():
    from apps.core.apply_sessions import capture_apply_shots, pick_form_context

    for page in playwright_page():
        page.goto(fixture_url("direct-form.html"))
        fields, _frame, issues = pick_form_context(page)
        shots = capture_apply_shots(page)

    assert [field["id"] for field in fields] == ["first_name", "email", "resume"]
    assert issues == []
    assert len(shots) == 1
    assert shots[0].startswith("data:image/jpeg;base64,")


def test_apply_session_prefers_iframe_form_fixture():
    from apps.core.apply_sessions import pick_form_context

    for page in playwright_page():
        page.goto(fixture_url("iframe-form.html"))
        fields, _frame, issues = pick_form_context(page)

    assert [field["id"] for field in fields] == ["full_name", "email", "linkedin"]
    assert issues == []


def test_apply_session_filters_listing_search_fixture():
    from apps.core.apply_sessions import apply_session_diagnostics, pick_form_context

    for page in playwright_page():
        page.goto(fixture_url("listing-search.html"))
        fields, _frame, issues = pick_form_context(page)
        diagnostics = apply_session_diagnostics(page, fields, issues)

    assert fields == []
    assert issues[0]["code"] == "listing-or-search-form"
    assert diagnostics["classification"] == "listing-search"
