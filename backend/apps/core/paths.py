from pathlib import Path

from django.conf import settings


def career_ops_root() -> Path:
    return Path(settings.CAREER_OPS_ROOT).resolve()


def root_path(*parts: str) -> Path:
    return career_ops_root().joinpath(*parts)


def root_script(name_no_ext: str) -> Path:
    return root_path("scripts", "js", f"{name_no_ext}.mjs")
