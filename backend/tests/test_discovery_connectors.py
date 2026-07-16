"""Connector parsing tests with injected fetch — no network."""

import pytest

from apps.discovery.connectors.apec import ApecConnector
from apps.discovery.connectors.ats_ashby import AshbyConnector
from apps.discovery.connectors.ats_greenhouse import GreenhouseConnector
from apps.discovery.connectors.ats_lever import LeverConnector
from apps.discovery.connectors.base import ConnectorError, SearchCriteria, build_connector
from apps.discovery.connectors.france_travail import FranceTravailConnector
from apps.discovery.connectors.hellowork import HelloWorkConnector, extract_job_postings
from apps.discovery.connectors.manual import IndeedManualConnector, LinkedInManualConnector
from apps.discovery.connectors.welcometothejungle import WelcomeToTheJungleConnector


class _Source:
    def __init__(self, config, connector=""):
        self.config = config
        self.connector = connector


def test_greenhouse_parses_board_jobs():
    payload = {"jobs": [
        {"id": 1, "title": "Data Engineer", "absolute_url": "https://boards.gh.io/acme/1",
         "location": {"name": "Paris"}, "updated_at": "2026-07-10T00:00:00Z", "content": "python"},
        {"id": 2, "title": "Sales Rep", "absolute_url": "https://boards.gh.io/acme/2",
         "location": {"name": "NYC"}, "updated_at": "2026-07-10T00:00:00Z"},
    ]}
    conn = GreenhouseConnector(source=_Source({"boards": ["acme"], "company": "Acme"}),
                               fetch=lambda url: payload)
    jobs = conn.search(SearchCriteria(target_titles=["Data Engineer"]))
    # Only the title-matching job survives the loose pre-filter.
    assert [j.title for j in jobs] == ["Data Engineer"]
    assert jobs[0].company == "Acme"
    assert jobs[0].location == "Paris"
    assert jobs[0].posted_at.isoformat() == "2026-07-10"


def test_lever_parses_postings():
    payload = [
        {"id": "x", "text": "AI Engineer", "hostedUrl": "https://jobs.lever.co/n/x",
         "categories": {"location": "Remote", "commitment": "Full-time"},
         "createdAt": 1_752_000_000_000, "descriptionPlain": "python"},
    ]
    conn = LeverConnector(source=_Source({"slugs": ["n"]}), fetch=lambda url: payload)
    jobs = conn.search(SearchCriteria(target_titles=["AI Engineer"]))
    assert len(jobs) == 1
    assert jobs[0].contract_type == "Full-time"
    assert jobs[0].location == "Remote"


def test_ashby_parses_jobs_and_marks_remote():
    payload = {"jobs": [
        {"id": "a", "title": "Machine Learning Engineer", "location": "Berlin",
         "isRemote": True, "employmentType": "FullTime", "jobUrl": "https://jobs.ashbyhq.com/x/a",
         "publishedAt": "2026-07-01T10:00:00Z", "descriptionPlain": "python"},
    ]}
    conn = AshbyConnector(source=_Source({"slugs": ["x"]}), fetch=lambda url: payload)
    jobs = conn.search(SearchCriteria(target_titles=["Machine Learning Engineer"]))
    assert "remote" in jobs[0].location.lower()


def test_france_travail_parses_resultats():
    payload = {"resultats": [
        {"id": "42", "intitule": "Ingénieur Data", "entreprise": {"nom": "Acme"},
         "lieuTravail": {"libelle": "Paris"}, "typeContratLibelle": "CDI",
         "salaire": {"libelle": "50k-60k"}, "dateCreation": "2026-07-12T09:00:00Z",
         "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/42"},
         "description": "python"},
    ]}
    conn = FranceTravailConnector(source=_Source({"access_token": "tok"}), fetch=lambda url: payload)
    jobs = conn.search(SearchCriteria(target_titles=["Data"]))
    assert jobs[0].company == "Acme"
    assert jobs[0].contract_type == "CDI"
    assert jobs[0].url.endswith("/offres/42")


def test_france_travail_refuses_live_run_without_credentials():
    conn = FranceTravailConnector(source=_Source({}))  # fetch defaults to default_fetch
    with pytest.raises(ConnectorError):
        conn.search(SearchCriteria(target_titles=["Data"]))


def test_greenhouse_error_on_all_boards_raises():
    def boom(url):
        raise RuntimeError("network down")

    conn = GreenhouseConnector(source=_Source({"boards": ["acme"]}), fetch=boom)
    with pytest.raises(ConnectorError):
        conn.search(SearchCriteria())


def test_build_connector_unknown_returns_none():
    assert build_connector(_Source({}, connector="nope")) is None


# --- APEC -------------------------------------------------------------------

def test_apec_parses_resultats():
    payload = {"resultats": [
        {"numeroOffre": "170123456W", "intitule": "Data Engineer Senior",
         "nomCommercial": "Acme", "lieuTexte": "Paris - 75", "nomTypeContrat": "CDI",
         "salaireTexte": "45 - 55 k€", "datePublication": "2026-07-10T00:00:00Z"},
        {"numeroOffre": "170123457W", "intitule": "Comptable", "nomCommercial": "Other",
         "lieuTexte": "Lyon", "nomTypeContrat": "CDI", "datePublication": "2026-07-10T00:00:00Z"},
    ]}
    conn = ApecConnector(source=_Source({}), fetch=lambda url, **kw: payload)
    jobs = conn.search(SearchCriteria(target_titles=["Data Engineer"]))
    assert [j.title for j in jobs] == ["Data Engineer Senior"]
    assert jobs[0].company == "Acme"
    assert jobs[0].contract_type == "CDI"
    assert jobs[0].url.endswith("/170123456W")
    assert jobs[0].posted_at.isoformat() == "2026-07-10"


def test_apec_network_error_raises_connector_error():
    def boom(url, **kw):
        raise RuntimeError("down")

    conn = ApecConnector(source=_Source({}), fetch=boom)
    with pytest.raises(ConnectorError):
        conn.search(SearchCriteria())


# --- Welcome to the Jungle --------------------------------------------------

def test_wttj_requires_algolia_keys():
    conn = WelcomeToTheJungleConnector(source=_Source({}), fetch=lambda url, **kw: {})
    with pytest.raises(ConnectorError):
        conn.search(SearchCriteria(target_titles=["Data"]))


def test_wttj_parses_hits():
    payload = {"results": [{"hits": [
        {"name": "AI Engineer", "organization": {"name": "Startup", "slug": "startup"},
         "slug": "ai-eng", "reference": "ref1", "offices": [{"city": "Paris"}],
         "contract_type": "FULL_TIME", "published_at": "2026-07-11T00:00:00Z",
         "remote": True, "description": "python"},
    ]}]}
    conn = WelcomeToTheJungleConnector(
        source=_Source({"app_id": "APPID", "api_key": "KEY"}), fetch=lambda url, **kw: payload
    )
    jobs = conn.search(SearchCriteria(target_titles=["AI Engineer"]))
    assert jobs[0].company == "Startup"
    assert "remote" in jobs[0].location.lower()
    assert jobs[0].url.endswith("/companies/startup/jobs/ai-eng")


# --- HelloWork (JSON-LD) ----------------------------------------------------

HELLOWORK_HTML = """
<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"ItemList","itemListElement":[
 {"@type":"JobPosting","title":"Data Engineer","url":"https://www.hellowork.com/o/1",
  "hiringOrganization":{"@type":"Organization","name":"Acme"},
  "jobLocation":{"@type":"Place","address":{"@type":"PostalAddress","addressLocality":"Paris"}},
  "employmentType":"FULL_TIME","datePosted":"2026-07-12",
  "baseSalary":{"@type":"MonetaryAmount","currency":"EUR","value":{"minValue":45000,"maxValue":55000}}},
 {"@type":"JobPosting","title":"Assistant RH","url":"https://www.hellowork.com/o/2",
  "hiringOrganization":{"name":"Other"},"datePosted":"2026-07-12"}
]}
</script></head><body></body></html>
"""


def test_hellowork_extracts_jobpostings_from_jsonld():
    postings = extract_job_postings(HELLOWORK_HTML)
    assert {p["title"] for p in postings} == {"Data Engineer", "Assistant RH"}


def test_hellowork_connector_filters_and_maps():
    conn = HelloWorkConnector(source=_Source({}), fetch=lambda url, **kw: HELLOWORK_HTML)
    jobs = conn.search(SearchCriteria(target_titles=["Data Engineer"]))
    assert [j.title for j in jobs] == ["Data Engineer"]
    assert jobs[0].company == "Acme"
    assert jobs[0].location == "Paris"
    assert "45000" in jobs[0].salary_text
    assert jobs[0].posted_at.isoformat() == "2026-07-12"


# --- Manual import (LinkedIn / Indeed) --------------------------------------

def test_linkedin_manual_reads_items_and_urls_without_network():
    config = {
        "items": [{"url": "https://linkedin.com/jobs/1", "title": "Data Engineer", "company": "Acme"}],
        "urls": ["https://linkedin.com/jobs/2"],
    }
    conn = LinkedInManualConnector(source=_Source(config))
    jobs = conn.search(SearchCriteria())  # no fetch provided — must not touch network
    assert len(jobs) == 2
    assert jobs[0].company == "Acme"
    assert jobs[1].url.endswith("/jobs/2")
    assert conn.slug == "linkedin"


def test_indeed_manual_empty_config_returns_nothing():
    conn = IndeedManualConnector(source=_Source({"items": [], "urls": []}))
    assert conn.search(SearchCriteria()) == []
    assert conn.slug == "indeed"
