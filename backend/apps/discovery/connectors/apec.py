"""APEC connector — cadres/tech, French market, high priority.

APEC exposes the public JSON search webservice its own site consumes
(``/cms/webservices/rechercheOffre``, POST). We use ONLY that documented public
endpoint with a light rate limit — no login, no anti-bot bypass.

Because the endpoint shape can drift and carries TOS considerations, the source
ships ``enabled=False`` and is opt-in. Parsing is fully covered by fixtures /
injected fetch so it stays offline-testable.
"""

from __future__ import annotations

from datetime import date, datetime

from .ats_greenhouse import title_matches
from .base import ConnectorError, JobConnector, RawJob, SearchCriteria, register

SEARCH_URL = "https://www.apec.fr/cms/webservices/rechercheOffre"
DETAIL_URL = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{ref}"


def _parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _first(offer: dict, *keys: str) -> str:
    for key in keys:
        value = offer.get(key)
        if isinstance(value, dict):
            value = value.get("nom") or value.get("libelle") or value.get("name")
        if value:
            return str(value)
    return ""


@register("apec")
class ApecConnector(JobConnector):
    slug = "apec"
    strategy = "api"

    def _build_payload(self, criteria: SearchCriteria) -> dict:
        return {
            "motsCles": " ".join(criteria.target_titles[:3]),
            "typeClient": "CADRE",
            "sorts": [{"type": "DATE", "direction": "DESCENDING"}],
            "pagination": {"range": min(criteria.max_results_per_run, 100), "startIndex": 0},
            "lieux": [str(loc) for loc in criteria.locations[:5]],
            "activeFiltre": True,
        }

    def search(self, criteria: SearchCriteria) -> list[RawJob]:
        try:
            payload = self.fetch(SEARCH_URL, method="POST", data=self._build_payload(criteria))
        except Exception as exc:
            raise ConnectorError(str(exc)) from exc

        terms = criteria.title_terms()
        results: list[RawJob] = []
        for offer in (payload or {}).get("resultats", []) or []:
            title = _first(offer, "intitule", "intituleOffre", "titre")
            if not title_matches(title, terms):
                continue
            ref = str(offer.get("numeroOffre") or offer.get("id") or "")
            url = str(offer.get("url") or (DETAIL_URL.format(ref=ref) if ref else ""))
            results.append(
                RawJob(
                    source_job_id=ref,
                    url=url,
                    title=title,
                    company=_first(offer, "nomCommercialEtablissement", "nomCommercial", "entreprise", "societe"),
                    location=_first(offer, "lieuTexte", "lieuxTexte", "villeLibelle", "lieu"),
                    contract_type=_first(offer, "nomTypeContrat", "typeContratLibelle", "typeContrat"),
                    salary_text=_first(offer, "salaireTexte", "salaire"),
                    posted_at=_parse_date(offer.get("datePublication") or offer.get("dateValidation")),
                    description=str(offer.get("texteHtml") or offer.get("descriptif") or ""),
                    apply_url=url,
                    raw_payload=offer if isinstance(offer, dict) else {},
                )
            )
        return results

    def capabilities(self) -> dict:
        return {"keywords": True, "location": True, "remote": False, "freshness": True, "pagination": True}
