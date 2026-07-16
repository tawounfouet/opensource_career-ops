from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class Identity(BaseModel):
    name: str
    title: str
    objective: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    mobility: str = ""
    driving_license: str = ""
    linkedin: str = ""
    linkedin_qr: str = ""


class Experience(BaseModel):
    start: str
    end: str
    role: str
    organization: str
    location: str = ""
    missions: list[str] = Field(default_factory=list)


class Education(BaseModel):
    year: str
    institution: str
    location: str = ""
    degree: str = ""
    field: str = ""


class Project(BaseModel):
    year: str
    title: str


class Language(BaseModel):
    language: str
    level: str
    note: str = ""


class CVData(BaseModel):
    meta: dict = Field(default_factory=dict)
    identity: Identity
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    regulations: list[str] = Field(default_factory=list)
    hard_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> "CVData":
        import json

        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(raw)

    def to_template_context(self) -> dict:
        return self.model_dump()
