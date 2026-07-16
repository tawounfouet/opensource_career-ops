from __future__ import annotations

import yaml

from .paths import root_path


FALLBACK_STATES = [
    {"id": "evaluated", "label": "Evaluated", "aliases": ["evaluada"], "group": "evaluated"},
    {"id": "applied", "label": "Applied", "aliases": ["aplicado", "enviada", "aplicada", "sent"], "group": "applied"},
    {"id": "responded", "label": "Responded", "aliases": ["respondido"], "group": "responded"},
    {"id": "interview", "label": "Interview", "aliases": ["entrevista"], "group": "interview"},
    {"id": "offer", "label": "Offer", "aliases": ["oferta"], "group": "offer"},
    {"id": "rejected", "label": "Rejected", "aliases": ["rechazado", "rechazada"], "group": "rejected"},
    {"id": "discarded", "label": "Discarded", "aliases": ["descartado", "descartada", "cerrada", "cancelada"], "group": "discarded"},
    {"id": "skip", "label": "SKIP", "aliases": ["no_aplicar", "no aplicar", "skip", "monitor"], "group": "skip"},
]


def read_canonical_states() -> list[dict]:
    try:
        doc = yaml.safe_load(root_path("templates", "states.yml").read_text(encoding="utf-8")) or {}
        states = doc.get("states")
        if isinstance(states, list) and states:
            return states
    except Exception:
        pass
    return FALLBACK_STATES


def canonicalize_status(raw: str) -> str | None:
    q = str(raw).strip().lower().replace("**", "")
    if not q:
        return None
    for state in read_canonical_states():
        label = str(state.get("label", ""))
        sid = str(state.get("id", ""))
        aliases = state.get("aliases") or []
        if label.lower() == q or sid.lower() == q or any(str(a).lower() == q for a in aliases):
            return label
    return None
