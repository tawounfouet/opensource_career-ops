from __future__ import annotations

import yaml
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.paths import root_path
from apps.core.safe_write import atomic_write_with_backup
from apps.core.services import run_node_script


def is_obj(value) -> bool:
    return isinstance(value, dict)


def deep_merge(dst, src):
    out = dict(dst) if isinstance(dst, dict) else {}
    for key, value in src.items():
        out[key] = deep_merge(out.get(key), value) if isinstance(value, dict) else value
    return out


def profile_patch_to_doc(patch: dict) -> dict:
    """Convert a flat or nested profile patch into a YAML-mergeable dict.

    Supports the full profile.yml schema: candidate, target_roles, narrative,
    compensation, location, language, cv, cover_letter, languages, interests,
    regulations, and all nested fields.
    """
    out: dict = {}

    # -- candidate block (flat shortcut) --
    candidate: dict = {}
    for key in ("full_name", "email", "phone", "location", "linkedin", "portfolio_url",
                "github", "twitter", "wechat", "photo"):
        if key in patch:
            candidate[key] = patch[key]
    # Legacy flat aliases
    if patch.get("name") and "full_name" not in candidate:
        candidate["full_name"] = patch["name"]
    if candidate:
        out["candidate"] = candidate

    # -- target_roles --
    if "target_roles" in patch:
        out["target_roles"] = patch["target_roles"]
    elif "roles" in patch and isinstance(patch["roles"], list):
        out["target_roles"] = {"primary": [str(r).strip() for r in patch["roles"] if str(r).strip()]}

    # -- narrative --
    if "narrative" in patch:
        out["narrative"] = patch["narrative"]
    else:
        narrative: dict = {}
        for key in ("headline", "exit_story", "objective"):
            if key in patch:
                narrative[key] = patch[key]
        if "superpowers" in patch:
            narrative["superpowers"] = patch["superpowers"]
        if "proof_points" in patch:
            narrative["proof_points"] = patch["proof_points"]
        if narrative:
            out["narrative"] = narrative

    # -- compensation --
    if "compensation" in patch:
        out["compensation"] = patch["compensation"]
    else:
        comp: dict = {}
        if patch.get("target_range"):
            comp["target_range"] = patch["target_range"]
        elif patch.get("compMin") and patch.get("compMax"):
            comp["target_range"] = f"{patch['compMin']}-{patch['compMax']}"
        if patch.get("currency"):
            comp["currency"] = patch["currency"]
        if patch.get("minimum"):
            comp["minimum"] = patch["minimum"]
        if patch.get("remote") or patch.get("location_flexibility"):
            comp["location_flexibility"] = patch.get("remote") or patch["location_flexibility"]
        if comp:
            out["compensation"] = comp

    # -- location --
    if "location" in patch and isinstance(patch["location"], dict):
        out["location"] = patch["location"]
    else:
        loc: dict = {}
        for key in ("country", "city", "timezone", "visa_status"):
            if key in patch:
                loc[key] = patch[key]
        if loc:
            out["location"] = loc

    # -- language (output language, not spoken languages) --
    if "language" in patch:
        out["language"] = patch["language"]

    # -- cv settings --
    if "cv" in patch:
        out["cv"] = patch["cv"]

    # -- cover_letter --
    if "cover_letter" in patch:
        out["cover_letter"] = patch["cover_letter"]

    # -- languages (spoken languages for CV) --
    if "languages" in patch:
        out["languages"] = patch["languages"]

    # -- interests --
    if "interests" in patch:
        out["interests"] = patch["interests"]

    # -- regulations --
    if "regulations" in patch:
        out["regulations"] = patch["regulations"]

    # -- spend_tier --
    if "spend_tier" in patch:
        out["spend_tier"] = patch["spend_tier"]

    return out


def _portal_to_dict(p) -> dict:
    """Serialize a Portal model to the YAML-shaped dict the frontend expects."""
    entry: dict = {"name": p.name, "careers_url": p.careers_url}
    if p.api_endpoint:
        entry["api"] = p.api_endpoint
    if p.scan_method and p.scan_method != "auto":
        entry["scan_method"] = p.scan_method
    if p.scan_query:
        entry["scan_query"] = p.scan_query
    if p.notes:
        entry["notes"] = p.notes
    if not p.enabled:
        entry["enabled"] = False
    entry.update(p.extra_config)
    return entry


def _job_board_to_dict(b) -> dict:
    """Serialize a JobBoard model to a dict."""
    entry: dict = {"name": b.name, "careers_url": b.careers_url}
    if b.provider:
        entry["provider"] = b.provider
    if not b.enabled:
        entry["enabled"] = False
    if b.notes:
        entry["notes"] = b.notes
    entry.update(b.extra_config)
    return entry


class PortalsView(APIView):
    kind = "portals"

    def get(self, request, *args, **kwargs):
        kind = kwargs.get("kind", self.kind)
        if kind == "profile":
            return self._get_profile()
        return self._get_portals()

    def _get_portals(self):
        from apps.portals.models import JobBoard, LocationFilter, Portal, SearchQuery, TitleFilter

        tf = TitleFilter.load()
        lf = LocationFilter.load()
        content = {
            "title_filter": {
                "positive": tf.positive,
                "negative": tf.negative,
                "seniority_boost": tf.seniority_boost,
            },
            "location_filter": {
                "allow": lf.allow,
                "block": lf.block,
                "always_allow": lf.always_allow,
            },
            "tracked_companies": [
                _portal_to_dict(p) for p in Portal.objects.all()
            ],
            "search_queries": [
                {"name": q.name, "query": q.query, "enabled": q.enabled}
                for q in SearchQuery.objects.all()
            ],
            "job_boards": [
                _job_board_to_dict(b) for b in JobBoard.objects.all()
            ],
        }
        return Response({"content": content, "exists": True})

    def _get_profile(self):
        path = root_path("config", "profile.yml")
        try:
            content = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return Response({"content": content, "exists": True})
        except FileNotFoundError:
            return Response({"content": {}, "exists": False})

    def post(self, request, *args, **kwargs):
        kind = kwargs.get("kind", self.kind)
        if kind == "profile":
            return self._post_profile(request.data)
        return self._post_portals(request.data)

    def _post_profile(self, data):
        proposed = profile_patch_to_doc(dict(data))
        if not proposed:
            return Response({"error": "nothing to write"}, status=400)
        path = root_path("config", "profile.yml")
        seeded = False
        if path.exists():
            try:
                base = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                return Response({"error": "config/profile.yml exists but is not valid YAML - refusing to overwrite it."}, status=409)
        else:
            try:
                base = yaml.safe_load(root_path("config", "profile.example.yml").read_text(encoding="utf-8")) or {}
                seeded = bool(base)
            except Exception:
                base = {}
        merged = deep_merge(base, proposed)
        atomic_write_with_backup(path, yaml.safe_dump(merged, sort_keys=False, allow_unicode=True, width=100))
        return Response({"ok": True, "seeded": seeded})

    def _post_portals(self, data):
        from apps.portals.models import TitleFilter
        from apps.portals.services import export_db_to_yaml

        roles = [str(r).strip() for r in data.get("roles", []) if str(r).strip()] if isinstance(data.get("roles"), list) else []
        if not roles:
            return Response({"error": "no roles"}, status=400)

        tf = TitleFilter.load()
        tf.positive = roles[:24]
        tf.save()

        if isinstance(data.get("location"), list) and data["location"]:
            from apps.portals.models import LocationFilter
            lf, _ = LocationFilter.objects.get_or_create(pk=1)
            lf.allow = [str(l).strip() for l in data["location"] if str(l).strip()]
            lf.save()

        export_db_to_yaml()
        return Response({"ok": True, "roles": len(roles[:24])})


class PortalVerifyView(APIView):
    def post(self, request):
        result = run_node_script("verify-portals")
        if result.returncode != 0:
            return Response({"error": result.stderr or result.stdout or "verify failed"}, status=500)
        return Response({"ok": True, "stdout": result.stdout})


# ------------------------------------------------------------------
# Profile views — read/write config/profile.yml + variants
# ------------------------------------------------------------------

def _load_profile_raw() -> dict:
    """Load the base profile YAML."""
    path = root_path("config", "profile.yml")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


def _save_profile_raw(data: dict) -> None:
    """Save the base profile YAML with backup."""
    path = root_path("config", "profile.yml")
    atomic_write_with_backup(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100))


def _list_variants() -> list[str]:
    """List all profile variant names (files in config/profiles/)."""
    profiles_dir = root_path("config", "profiles")
    if not profiles_dir.exists():
        return []
    return sorted(
        p.stem for p in profiles_dir.glob("*.yml")
    )


def _load_variant(name: str) -> dict:
    """Load a profile variant YAML."""
    path = root_path("config", "profiles", f"{name}.yml")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


def _save_variant(name: str, data: dict) -> None:
    """Save a profile variant YAML with backup."""
    profiles_dir = root_path("config", "profiles")
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / f"{name}.yml"
    atomic_write_with_backup(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100))


def _resolve_profile(variant_name: str | None = None) -> dict:
    """Resolve the final profile: base + optional variant override."""
    base = _load_profile_raw()
    if variant_name:
        override = _load_variant(variant_name)
        if override:
            return deep_merge(base, override)
    return base


class ProfileView(APIView):
    """Read/write config/profile.yml with optional variant support.

    GET  /api/profile?variant=data-engineer  → resolved profile (base + variant)
    GET  /api/profile                         → base profile only
    PATCH /api/profile                        → partial update (writes to base)
    """

    def get(self, request):
        variant = request.query_params.get("variant")
        profile = _resolve_profile(variant)
        variants = _list_variants()
        return Response({
            "profile": profile,
            "variants": variants,
            "active_variant": variant,
        })

    def patch(self, request):
        data = request.data
        if not data:
            return Response({"error": "empty body"}, status=400)

        # If variant is specified, write to the variant file
        variant = request.query_params.get("variant")
        if variant:
            existing = _load_variant(variant)
            merged = deep_merge(existing, data)
            _save_variant(variant, merged)
        else:
            existing = _load_profile_raw()
            merged = deep_merge(existing, data)
            _save_profile_raw(merged)

        return Response({"ok": True, "variant": variant})


class ProfileVariantView(APIView):
    """Manage profile variants (config/profiles/*.yml).

    GET    /api/profile/variants           → list variants with their content
    POST   /api/profile/variants           → create a variant
    DELETE /api/profile/variants/{name}    → delete a variant
    """

    def get(self, request):
        variants = _list_variants()
        result = []
        for name in variants:
            content = _load_variant(name)
            result.append({"name": name, "overrides": content})
        return Response({"variants": result})

    def post(self, request):
        name = request.data.get("name", "").strip()
        if not name:
            return Response({"error": "name is required"}, status=400)
        # Sanitize name: alphanumeric + hyphens
        import re
        name = re.sub(r"[^a-zA-Z0-9-]", "-", name).strip("-").lower()
        if not name:
            return Response({"error": "invalid name"}, status=400)

        overrides = request.data.get("overrides", {})
        _save_variant(name, overrides)
        return Response({"ok": True, "name": name})

    def delete(self, request, name: str):
        path = root_path("config", "profiles", f"{name}.yml")
        if path.exists():
            path.unlink()
            return Response({"ok": True})
        return Response({"error": "variant not found"}, status=404)
