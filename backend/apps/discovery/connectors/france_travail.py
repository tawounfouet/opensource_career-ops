"""France Travail (ex-Pôle emploi) "Offres d'emploi v2" connector.

This is the highest-volume public French source, but its API requires
registered OAuth client credentials. V1 policy: the connector parses the
official response shape (so fixtures/tests work), but a LIVE run refuses to
proceed without credentials rather than scraping the public site.

Config:
- ``config["access_token"]``: a bearer token (obtained out-of-band / V2 OAuth).
- ``config["search_url"]`` (optional): override the search endpoint.
Provide an injected ``fetch`` in tests to exercise parsing offline.
"""

from __future__ import annotations

from datetime import date, datetime

from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"


def _parse_iso(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


@register("france_travail")
class FranceTravailConnector(JobConnector):
    slug = "france_travail"
    strategy = "api"

    def _build_url(self, criteria: SearchCriteria) -> str:
        base = self.config.get("search_url") or SEARCH_URL
        mots = ",".join(criteria.target_titles[:3]) if criteria.target_titles else ""
        params = []
        if mots:
            params.append(f"motsCles={mots}")
        params.append(f"maxCreationDate={criteria.freshness_days}")
        params.append(f"range=0-{max(0, min(criteria.max_results_per_run, 150) - 1)}")
        return base + ("?" + "&".join(params) if params else "")

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        # A live run needs credentials; the injected test fetch bypasses this.
        if self.fetch.__name__ == "default_fetch" and not self.config.get("access_token"):
            raise ConnectorError(
                "France Travail requires API credentials (register an app and set config.access_token)."
            )
        try:
            payload = self.fetch(self._build_url(criteria))
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc

        results: list[RawJob] = []
        for offer in (payload or {}).get("resultats", []) or []:
            entreprise = offer.get("entreprise") or {}
            lieu = offer.get("lieuTravail") or {}
            salaire = offer.get("salaire") or {}
            origine = offer.get("origineOffre") or {}
            results.append(
                RawJob(
                    source_job_id=str(offer.get("id") or ""),
                    url=str(origine.get("urlOrigine") or ""),
                    title=str(offer.get("intitule") or ""),
                    company=str(entreprise.get("nom") or ""),
                    location=str(lieu.get("libelle") or ""),
                    contract_type=str(offer.get("typeContratLibelle") or offer.get("typeContrat") or ""),
                    salary_text=str(salaire.get("libelle") or ""),
                    posted_at=_parse_iso(offer.get("dateCreation")),
                    description=str(offer.get("description") or ""),
                    apply_url=str(origine.get("urlOrigine") or ""),
                    raw_payload=offer if isinstance(offer, dict) else {},
                )
            )
        return results

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": False, "freshness": True, "pagination": True}
