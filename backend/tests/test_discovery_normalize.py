"""Unit tests for deterministic normalization + scoring + dedup keys (no DB)."""

from datetime import date, timedelta
from types import SimpleNamespace

from apps.discovery.connectors.base import RawJob, SearchCriteria
from apps.discovery.services.normalize import (
    canonical_key,
    canonical_url,
    detect_contract,
    detect_language,
    detect_remote,
    extract_salary,
    normalize_job,
)
from apps.discovery.services.scoring import score_job


# --- normalize primitives ---------------------------------------------------

def test_detect_remote_full_vs_hybrid_vs_onsite():
    assert detect_remote("Ingénieur Data - Full Remote") == "remote"
    assert detect_remote("Poste hybride 2 jours de télétravail") == "hybrid"
    assert detect_remote("Sur site à Paris, présentiel") == "onsite"
    assert detect_remote("Data Engineer") == "unknown"
    # A bare "remote" mention downgrades to hybrid, never overclaims full remote.
    assert detect_remote("Some remote flexibility possible") == "hybrid"


def test_detect_contract_from_hint_and_text():
    assert detect_contract("full-time") == "cdi"
    assert detect_contract("", "Contrat CDI à pourvoir") == "cdi"
    assert detect_contract("", "Mission freelance 6 mois") == "freelance"
    assert detect_contract("", "Offre d'alternance") == "alternance"
    assert detect_contract("", "Stage de fin d'études") == "stage"
    assert detect_contract("", "Nothing here") == "unknown"


def test_extract_salary_ranges_and_singles():
    assert extract_salary("45k-55k €") == (45000, 55000, "EUR")
    assert extract_salary("55 000 € brut annuel")[0] == 55000
    assert extract_salary("Rémunération 60k€")[:2] == (60000, None)
    # Never invent: no salary text → nothing.
    assert extract_salary("Pas de salaire indiqué") == (None, None, "")
    # A stray year must not be read as salary.
    assert extract_salary("Poste ouvert en 2024") == (None, None, "")


def test_canonical_url_strips_www_query_and_trailing_slash():
    assert canonical_url("https://WWW.Example.com/jobs/42/?utm_source=x") == "https://example.com/jobs/42"


def test_detect_language_fr_vs_en():
    assert detect_language("Nous recherchons un ingénieur pour rejoindre notre équipe") == "fr"
    assert detect_language("We are looking for an engineer to join the team") == "en"


def test_normalize_job_end_to_end():
    raw = RawJob(
        source_job_id="1",
        url="https://boards.example.com/acme/jobs/1?utm_medium=rss",
        title="Senior Data Engineer  ",
        company="Acme SAS",
        location="Paris, France",
        salary_text="50k-65k €",
        posted_at=date(2026, 7, 14),
        description="Full remote. CDI. Python, Spark.",
    )
    norm = normalize_job(raw, market="france")
    assert norm["title"] == "Senior Data Engineer"
    assert norm["company"] == "Acme"
    assert norm["company_slug"] == "acme"
    assert norm["remote_type"] == "remote"
    assert norm["contract_type"] == "cdi"
    assert norm["salary_min"] == 50000 and norm["salary_max"] == 65000
    assert norm["seniority"] == "senior"
    assert canonical_key(norm) == "acme|senior-data-engineer|paris"


# --- scoring ----------------------------------------------------------------

def _profile(**over):
    base = dict(
        target_titles=["Data Engineer"],
        blocked_titles=[],
        positive_keywords=["python"],
        required_keywords=[],
        negative_keywords=["php"],
        remote_policy="any",
        locations=["Paris"],
        contract_types=["cdi"],
        salary_min=None,
        companies_allow=[],
        companies_block=[],
    )
    base.update(over)
    return SimpleNamespace(**base)


def _job(**over):
    base = dict(
        title="Data Engineer",
        company="Acme",
        location="Paris",
        remote_type="remote",
        contract_type="cdi",
        salary_min=None,
        salary_max=None,
        description_text="python spark",
        requirements_text="",
        posted_at=date.today(),
    )
    base.update(over)
    return base


def test_score_exact_title_and_keywords_high():
    result = score_job(_job(), _profile(), date.today())
    assert not result["rejected"]
    assert result["title_score"] == 20
    assert result["score"] >= 70


def test_score_rejects_blocked_company():
    result = score_job(_job(), _profile(companies_block=["Acme"]), date.today())
    assert result["rejected"] and result["reject_reason"] == "blocked company"


def test_score_rejects_missing_required_keyword():
    result = score_job(_job(description_text="java only"), _profile(required_keywords=["python"]), date.today())
    assert result["rejected"]
    assert "python" in result["reject_reason"]


def test_score_rejects_onsite_when_remote_only():
    result = score_job(_job(remote_type="onsite"), _profile(remote_policy="remote"), date.today())
    assert result["rejected"] and "remote" in result["reject_reason"]


def test_score_negative_keyword_penalizes():
    clean = score_job(_job(), _profile(), date.today())
    dirty = score_job(_job(description_text="python php legacy"), _profile(), date.today())
    assert dirty["negative_penalty"] < 0
    assert dirty["score"] < clean["score"]


def test_score_stage_rejected_when_not_wanted():
    result = score_job(_job(contract_type="stage"), _profile(contract_types=["cdi"]), date.today())
    assert result["rejected"] and "contract" in result["reject_reason"]


def test_freshness_decays_with_age():
    fresh = score_job(_job(posted_at=date.today()), _profile(), date.today())
    old = score_job(_job(posted_at=date.today() - timedelta(days=30)), _profile(), date.today())
    assert fresh["freshness_score"] == 20
    assert old["freshness_score"] == 2


def test_criteria_title_terms_lowercased():
    crit = SearchCriteria(target_titles=["Senior Data Engineer"])
    assert crit.title_terms() == ["data", "engineer", "senior"]
