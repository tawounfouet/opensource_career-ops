"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Award,
  Brain,
  BookOpen,
  GraduationCap,
  Loader2,
  List,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Dashboard = {
  experiences: number;
  competencies: number;
  evidence: number;
  educations: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  without_evidence: number;
};

type Experience = {
  id: number;
  title: string;
  type: string;
  organization: string;
  description: string;
  deliverables: string[];
  outcomes: string[];
  tools: string[];
  competencies_count?: number;
};

type Competency = {
  id: number;
  label: string;
  formulation: string;
  category: "knowledge" | "hard_skill" | "soft_skill";
  mastery_level: "beginner" | "junior" | "confirmed" | "expert";
  confidence: "low" | "medium" | "high";
  status: "draft" | "validated" | "rejected" | "archived";
  experience_ids?: number[];
  evidence_ids?: number[];
  evidence_detail?: Evidence[];
};

type Evidence = {
  id: number;
  title: string;
  type: string;
  description: string;
  source_experience: number | null;
};

const CATEGORY_LABELS = {
  knowledge: "Savoir",
  hard_skill: "Savoir-faire",
  soft_skill: "Savoir-être",
};

const LEVEL_LABELS = {
  beginner: "Débutant",
  junior: "Junior",
  confirmed: "Confirmé",
  expert: "Expert",
};

const TYPE_LABELS: Record<string, string> = {
  professional: "Professionnel",
  project: "Projet",
  education: "Formation",
  volunteer: "Bénévolat",
  personal: "Personnel",
  travel: "Voyage",
  cultural: "Culturel",
  other: "Autre",
};

function splitList(value: string): string[] {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  const message = typeof data === "object" && data !== null && "error" in data ? String((data as { error?: unknown }).error || "") : "";
  if (!res.ok || message) throw new Error(message || `Request failed (${res.status})`);
  return data as T;
}

async function fetchJsonSafe<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return data as T;
}

export function SkillsPortfolioView() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState("");

  // LLM state
  const [llmBusy, setLlmBusy] = useState(false);
  const [extractResult, setExtractResult] = useState<string>("");

  // Benchmark state
  const [jdText, setJdBenchmarkText] = useState("");
  const [benchmarkResult, setBenchmarkResult] = useState<string>("");
  const [targetRole, setTargetRole] = useState("");

  // Integration state
  const [cvBulletsResult, setCvBulletsResult] = useState<string>("");
  const [interviewResult, setInterviewResult] = useState<string>("");
  const [discoveryResult, setDiscoveryResult] = useState<string>("");

  // CV generation state
  const [cvResult, setCvResult] = useState<string>("");
  const [cvFormat, setCvFormat] = useState<"markdown" | "json">("markdown");

  const [experienceDraft, setExperienceDraft] = useState({
    title: "",
    type: "professional",
    organization: "",
    description: "",
    deliverables: "",
    outcomes: "",
    tools: "",
  });
  const [competencyDraft, setCompetencyDraft] = useState({
    label: "",
    formulation: "",
    category: "hard_skill",
    mastery_level: "junior",
    confidence: "medium",
    experience_id: "",
  });
  const [evidenceDraft, setEvidenceDraft] = useState({
    title: "",
    type: "deliverable",
    description: "",
    source_experience: "",
    competency_id: "",
  });

  const [educations, setEducations] = useState<Array<{ id: number; title: string; competencies_count: number }>>([]);
  const [educationDraft, setEducationDraft] = useState({
    title: "",
    institution: "",
    education_type: "formation",
    status: "completed",
    start_date: "",
    end_date: "",
    credential_url: "",
    hours: "",
    description: "",
  });

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchJson<Dashboard>("/api/skills/dashboard"),
      fetchJson<{ experiences: Experience[] }>("/api/skills/experiences"),
      fetchJson<{ competencies: Competency[] }>("/api/skills/competencies"),
      fetchJson<{ evidence: Evidence[] }>("/api/skills/evidence"),
      fetchJson<{ educations: Array<{ id: number; title: string; competencies_count: number }> }>("/api/skills/educations"),
    ])
      .then(([dash, exp, comp, ev, edu]) => {
        setDashboard(dash);
        setExperiences(exp.experiences);
        setCompetencies(comp.competencies);
        setEvidence(ev.evidence);
        setEducations(edu.educations);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Chargement impossible"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const validated = dashboard?.by_status.validated ?? 0;
  const draft = dashboard?.by_status.draft ?? 0;

  const latestExperienceId = useMemo(() => experiences[0]?.id ? String(experiences[0].id) : "", [experiences]);

  const createExperience = () => {
    setSaving(true);
    setError("");
    fetchJson<Experience>("/api/skills/experiences", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: experienceDraft.title,
        type: experienceDraft.type,
        organization: experienceDraft.organization,
        description: experienceDraft.description,
        deliverables: splitList(experienceDraft.deliverables),
        outcomes: splitList(experienceDraft.outcomes),
        tools: splitList(experienceDraft.tools),
      }),
    })
      .then(() => {
        setExperienceDraft({ title: "", type: "professional", organization: "", description: "", deliverables: "", outcomes: "", tools: "" });
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Création expérience impossible"))
      .finally(() => setSaving(false));
  };

  const createCompetency = () => {
    setSaving(true);
    setError("");
    const selectedExperienceId = competencyDraft.experience_id || latestExperienceId;
    fetchJson<Competency>("/api/skills/competencies", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: competencyDraft.label,
        formulation: competencyDraft.formulation,
        category: competencyDraft.category,
        mastery_level: competencyDraft.mastery_level,
        confidence: competencyDraft.confidence,
        status: "draft",
        experience_ids: selectedExperienceId ? [Number(selectedExperienceId)] : [],
      }),
    })
      .then(() => {
        setCompetencyDraft({ label: "", formulation: "", category: "hard_skill", mastery_level: "junior", confidence: "medium", experience_id: latestExperienceId });
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Création compétence impossible"))
      .finally(() => setSaving(false));
  };

  const createEvidence = () => {
    setSaving(true);
    setError("");
    fetchJson<Evidence>("/api/skills/evidence", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: evidenceDraft.title,
        type: evidenceDraft.type,
        description: evidenceDraft.description,
        source_experience: evidenceDraft.source_experience ? Number(evidenceDraft.source_experience) : null,
      }),
    })
      .then((created) => {
        const competencyId = Number(evidenceDraft.competency_id);
        if (!competencyId) return null;
        const target = competencies.find((competency) => competency.id === competencyId);
        const currentEvidence = target?.evidence_detail?.map((item) => item.id) ?? [];
        return fetchJson<Competency>(`/api/skills/competencies/${competencyId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            evidence_ids: [...currentEvidence, created.id],
          }),
        });
      })
      .then(() => {
        setEvidenceDraft({ title: "", type: "deliverable", description: "", source_experience: "", competency_id: "" });
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Création preuve impossible"))
      .finally(() => setSaving(false));
  };

  const createEducation = () => {
    setSaving(true);
    setError("");
    fetchJson<{ id: number }>("/api/skills/educations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: educationDraft.title,
        institution: educationDraft.institution,
        education_type: educationDraft.education_type,
        status: educationDraft.status,
        start_date: educationDraft.start_date || null,
        end_date: educationDraft.end_date || null,
        credential_url: educationDraft.credential_url,
        hours: educationDraft.hours ? Number(educationDraft.hours) : null,
        description: educationDraft.description,
      }),
    })
      .then(() => {
        setEducationDraft({ title: "", institution: "", education_type: "formation", status: "completed", start_date: "", end_date: "", credential_url: "", hours: "", description: "" });
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Création formation impossible"))
      .finally(() => setSaving(false));
  };

  const validateCompetency = (competency: Competency) => {
    setBusyId(competency.id);
    setError("");
    fetchJson<Competency>(`/api/skills/competencies/${competency.id}/validate`, { method: "POST" })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Validation impossible"))
      .finally(() => setBusyId(null));
  };

  // --- LLM Actions ---

  const extractFromExperience = (experienceId: number) => {
    setLlmBusy(true);
    setError("");
    setExtractResult("");
    fetchJsonSafe<{ extracted: unknown[]; created: unknown[]; count: number; error?: string }>(`/api/skills/llm/extract-from-experience`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ experience_id: experienceId, persist: true }),
    })
      .then((result) => {
        if (result.error) {
          setExtractResult(`Erreur : ${result.error}`);
        } else {
          setExtractResult(`${result.count} compétence(s) extraite(s) et créée(s).`);
          load();
        }
      })
      .catch((e: unknown) => { setExtractResult(`Erreur : ${e instanceof Error ? e.message : "Extraction LLM échouée"}`); })
      .finally(() => setLlmBusy(false));
  };

  const runBenchmark = () => {
    if (!targetRole.trim() || !jdText.trim()) return;
    setLlmBusy(true);
    setError("");
    setBenchmarkResult("");
    fetchJsonSafe<{ overall_match: string; gaps: unknown[]; strengths: unknown[]; error?: string }>(`/api/skills/llm/benchmark-summary`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: targetRole, jd_text: jdText }),
    })
      .then((result) => {
        if (result.error) {
          setBenchmarkResult(`Erreur : ${result.error}`);
        } else {
          setBenchmarkResult(JSON.stringify(result, null, 2));
        }
      })
      .catch((e: unknown) => { setBenchmarkResult(`Erreur : ${e instanceof Error ? e.message : "Benchmark échoué"}`); })
      .finally(() => setLlmBusy(false));
  };

  const generateCvBullets = () => {
    if (!targetRole.trim()) return;
    setLlmBusy(true);
    setError("");
    setCvBulletsResult("");
    fetchJsonSafe<{ bullets: string[]; error?: string }>(`/api/skills/llm/suggest-cv-bullets`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: targetRole }),
    })
      .then((result) => {
        if (result.error) {
          setCvBulletsResult(`Erreur : ${result.error}`);
        } else {
          setCvBulletsResult(result.bullets.join("\n"));
        }
      })
      .catch((e: unknown) => { setCvBulletsResult(`Erreur : ${e instanceof Error ? e.message : "CV bullets échoué"}`); })
      .finally(() => setLlmBusy(false));
  };

  const generateInterviewQuestions = () => {
    if (!targetRole.trim()) return;
    setLlmBusy(true);
    setError("");
    setInterviewResult("");
    fetchJsonSafe<{ questions: string[]; error?: string }>(`/api/skills/llm/suggest-interview-questions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_role: targetRole }),
    })
      .then((result) => {
        if (result.error) {
          setInterviewResult(`Erreur : ${result.error}`);
        } else {
          setInterviewResult(result.questions.join("\n"));
        }
      })
      .catch((e: unknown) => { setInterviewResult(`Erreur : ${e instanceof Error ? e.message : "Questions entretien échouées"}`); })
      .finally(() => setLlmBusy(false));
  };

  const generateDiscoveryProfile = () => {
    setLlmBusy(true);
    setError("");
    setDiscoveryResult("");
    fetchJsonSafe<{ keywords: string[]; search_profiles: unknown[]; error?: string }>(`/api/skills/llm/discovery-profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    })
      .then((result) => {
        if (result.error) {
          setDiscoveryResult(`Erreur : ${result.error}`);
        } else {
          setDiscoveryResult(JSON.stringify(result, null, 2));
        }
      })
      .catch((e: unknown) => { setDiscoveryResult(`Erreur : ${e instanceof Error ? e.message : "Profil discovery échoué"}`); })
      .finally(() => setLlmBusy(false));
  };

  const generateCv = (format: "markdown" | "json") => {
    setLlmBusy(true);
    setError("");
    setCvResult("");
    setCvFormat(format);
    const endpoint = format === "json" ? "/api/skills/export/cvdata" : "/api/skills/export/cv-markdown";
    fetchJsonSafe<string>(endpoint, { method: "GET" })
      .then((result) => {
        setCvResult(typeof result === "string" ? result : JSON.stringify(result, null, 2));
      })
      .catch((e: unknown) => { setCvResult(`Erreur : ${e instanceof Error ? e.message : "Génération CV échouée"}`); })
      .finally(() => setLlmBusy(false));
  };

  const downloadCv = () => {
    if (!cvResult) return;
    const ext = cvFormat === "json" ? "json" : "md";
    const mime = cvFormat === "json" ? "application/json" : "text/markdown";
    const blob = new Blob([cvResult], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cv.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <Brain className="size-3.5 text-brand" />
              Expériences · compétences · preuves
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Portefeuille de compétences
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Formalise ce que tu sais faire à partir de situations vécues. Une compétence ne devient exploitable que lorsqu'elle est reliée à une preuve.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/skills/list"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              <List className="size-4" />
              Compétences
            </Link>
            <Link
              href="/skills/experiences"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              <BookOpen className="size-4" />
              Expériences
            </Link>
            <Link
              href="/skills/education"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              <GraduationCap className="size-4" />
              Formations
            </Link>
            <button
              type="button"
              onClick={load}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-60"
            >
              <RefreshCw className={cn("size-4", loading && "animate-spin")} />
              Rafraîchir
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-5 py-6 md:px-10">
        {error && <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300">{error}</div>}

        <div className="mb-6 grid gap-3 md:grid-cols-6">
          <Stat icon={BookOpen} label="Expériences" value={String(dashboard?.experiences ?? 0)} />
          <Stat icon={Brain} label="Compétences" value={String(dashboard?.competencies ?? 0)} />
          <Stat icon={ShieldCheck} label="Validées" value={String(validated)} />
          <Stat icon={Sparkles} label="Draft" value={String(draft)} />
          <Stat icon={Award} label="Sans preuve" value={String(dashboard?.without_evidence ?? 0)} />
          <Stat icon={GraduationCap} label="Formations" value={String(dashboard?.educations ?? 0)} />
        </div>

        {loading ? (
          <div className="grid min-h-96 place-items-center rounded-3xl border border-border bg-surface/50">
            <div className="flex items-center gap-3 text-muted">
              <Loader2 className="size-5 animate-spin text-brand" />
              Chargement du portefeuille...
            </div>
          </div>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
            {/* ---- SIDEBAR: formulaires ---- */}
            <aside className="space-y-4">
              <Panel title="Ajouter une expérience">
                <Input label="Titre" value={experienceDraft.title} onChange={(value) => setExperienceDraft((d) => ({ ...d, title: value }))} placeholder="Projet Django discovery" />
                <Input label="Organisation" value={experienceDraft.organization} onChange={(value) => setExperienceDraft((d) => ({ ...d, organization: value }))} placeholder="Perso, entreprise, école..." />
                <Textarea label="Description" value={experienceDraft.description} onChange={(value) => setExperienceDraft((d) => ({ ...d, description: value }))} placeholder="Contexte, rôle, responsabilités..." />
                <Textarea label="Livrables" value={experienceDraft.deliverables} onChange={(value) => setExperienceDraft((d) => ({ ...d, deliverables: value }))} placeholder="Un élément par ligne" rows={3} />
                <button type="button" onClick={createExperience} disabled={saving || !experienceDraft.title.trim()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60">
                  {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                  Créer l'expérience
                </button>
              </Panel>

              {experiences.length > 0 ? (
                <Panel title="Extraction LLM">
                  <p className="text-xs text-muted">Sélectionne une expérience pour extraire automatiquement des compétences via l'IA.</p>
                  <Select label="Expérience" value={latestExperienceId} onChange={() => {}} options={experiences.map((exp) => [String(exp.id), exp.title])} />
                  <button type="button" onClick={() => extractFromExperience(Number(latestExperienceId))} disabled={llmBusy || !latestExperienceId} className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2.5 text-sm font-semibold text-brand-text transition hover:bg-brand/15 disabled:opacity-60">
                    {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                    Extraire les compétences
                  </button>
                  {extractResult && <p className={cn("text-xs", extractResult.startsWith("Erreur") ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400")}>{extractResult}</p>}
                </Panel>
              ) : (
                <Panel title="Commencer ici">
                  <p className="text-sm text-muted">Ajoute une expérience ci-dessus, puis reviens ici pour extraire automatiquement des compétences via l'IA.</p>
                </Panel>
              )}

              <Panel title="Ajouter une compétence">
                <Input label="Libellé" value={competencyDraft.label} onChange={(value) => setCompetencyDraft((d) => ({ ...d, label: value }))} placeholder="Concevoir une API Django" />
                <Textarea label="Formulation" value={competencyDraft.formulation} onChange={(value) => setCompetencyDraft((d) => ({ ...d, formulation: value }))} placeholder="Je suis capable de..." rows={4} />
                <Select label="Catégorie" value={competencyDraft.category} onChange={(value) => setCompetencyDraft((d) => ({ ...d, category: value }))} options={[["knowledge", "Savoir"], ["hard_skill", "Savoir-faire"], ["soft_skill", "Savoir-être"]]} />
                <Select label="Niveau" value={competencyDraft.mastery_level} onChange={(value) => setCompetencyDraft((d) => ({ ...d, mastery_level: value }))} options={[["beginner", "Débutant"], ["junior", "Junior"], ["confirmed", "Confirmé"], ["expert", "Expert"]]} />
                <Select label="Expérience source" value={competencyDraft.experience_id || latestExperienceId} onChange={(value) => setCompetencyDraft((d) => ({ ...d, experience_id: value }))} options={experiences.map((exp) => [String(exp.id), exp.title])} />
                <button type="button" onClick={createCompetency} disabled={saving || !competencyDraft.label.trim() || !competencyDraft.formulation.trim()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60">
                  {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                  Créer la compétence draft
                </button>
              </Panel>

              <Panel title="Ajouter une preuve">
                <Input label="Titre" value={evidenceDraft.title} onChange={(value) => setEvidenceDraft((d) => ({ ...d, title: value }))} placeholder="Endpoint testé, livrable, feedback..." />
                <Select label="Type" value={evidenceDraft.type} onChange={(value) => setEvidenceDraft((d) => ({ ...d, type: value }))} options={[["deliverable", "Livrable"], ["metric", "Métrique"], ["feedback", "Feedback"], ["certificate", "Certificat"], ["document", "Document"], ["other", "Autre"]]} />
                <Select label="Expérience source" value={evidenceDraft.source_experience} onChange={(value) => setEvidenceDraft((d) => ({ ...d, source_experience: value }))} options={experiences.map((exp) => [String(exp.id), exp.title])} />
                <Select label="Compétence à relier" value={evidenceDraft.competency_id} onChange={(value) => setEvidenceDraft((d) => ({ ...d, competency_id: value }))} options={competencies.map((comp) => [String(comp.id), comp.label])} />
                <Textarea label="Description" value={evidenceDraft.description} onChange={(value) => setEvidenceDraft((d) => ({ ...d, description: value }))} placeholder="Ce que cette preuve démontre concrètement." rows={3} />
                <button type="button" onClick={createEvidence} disabled={saving || !evidenceDraft.title.trim()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60">
                  {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                  Créer la preuve
                </button>
              </Panel>

              <Panel title="Ajouter une formation">
                <Input label="Titre" value={educationDraft.title} onChange={(value) => setEducationDraft((d) => ({ ...d, title: value }))} placeholder="Master IA, AWS SAA, BTS SIO..." />
                <Input label="Organisme" value={educationDraft.institution} onChange={(value) => setEducationDraft((d) => ({ ...d, institution: value }))} placeholder="Universite, organisme de certif..." />
                <Select label="Type" value={educationDraft.education_type} onChange={(value) => setEducationDraft((d) => ({ ...d, education_type: value }))} options={[["formation", "Formation"], ["certification", "Certification"], ["rncp", "Titre RNCP"], ["professional", "Formation pro"], ["mooc", "MOOC"]]} />
                <Select label="Statut" value={educationDraft.status} onChange={(value) => setEducationDraft((d) => ({ ...d, status: value }))} options={[["completed", "Terminee"], ["in_progress", "En cours"], ["planned", "Planifiee"]]} />
                <div className="grid grid-cols-2 gap-3">
                  <Input label="Debut" value={educationDraft.start_date} onChange={(value) => setEducationDraft((d) => ({ ...d, start_date: value }))} placeholder="YYYY-MM-DD" />
                  <Input label="Fin" value={educationDraft.end_date} onChange={(value) => setEducationDraft((d) => ({ ...d, end_date: value }))} placeholder="YYYY-MM-DD" />
                </div>
                <Input label="Heures" value={educationDraft.hours} onChange={(value) => setEducationDraft((d) => ({ ...d, hours: value }))} placeholder="600" />
                <Input label="URL certificat" value={educationDraft.credential_url} onChange={(value) => setEducationDraft((d) => ({ ...d, credential_url: value }))} placeholder="https://..." />
                <button type="button" onClick={createEducation} disabled={saving || !educationDraft.title.trim()} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60">
                  {saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}
                  Créer la formation
                </button>
              </Panel>
            </aside>

            {/* ---- MAIN: résumé + actions rapides ---- */}
            <section className="space-y-4">
              {/* Résumé rapide des compétences */}
              <Panel title="Dernières activités">
                {competencies.length === 0 ? (
                  <p className="text-sm text-muted">Aucune compétence. Crée-en une dans la barre latérale ou utilise l'extraction LLM.</p>
                ) : (
                  <div className="space-y-2">
                    {competencies.slice(0, 10).map((competency) => (
                      <div key={competency.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/55 px-4 py-2.5">
                        <span className={cn("size-2 shrink-0 rounded-full", competency.status === "validated" ? "bg-emerald-500" : competency.status === "rejected" ? "bg-red-500" : "bg-amber-400")} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground">{competency.label}</p>
                          <p className="truncate text-xs text-muted">{CATEGORY_LABELS[competency.category]} · {LEVEL_LABELS[competency.mastery_level]} · {competency.evidence_detail?.length ?? 0} preuve(s)</p>
                        </div>
                        <span className={cn("shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold", competency.status === "validated" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : competency.status === "rejected" ? "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300" : "border-border bg-surface text-muted")}>
                          {competency.status}
                        </span>
                        {competency.status !== "validated" && (
                          <button type="button" onClick={() => validateCompetency(competency)} disabled={busyId === competency.id} className="shrink-0 rounded-lg border border-brand/30 bg-brand-soft px-2 py-1 text-[10px] font-semibold text-brand-text transition hover:bg-brand/15 disabled:opacity-60">
                            {busyId === competency.id ? <Loader2 className="size-3 animate-spin" /> : "Valider"}
                          </button>
                        )}
                      </div>
                    ))}
                    {competencies.length > 10 && (
                      <Link href="/skills/list" className="block text-center text-xs text-brand hover:underline">
                        Voir les {competencies.length} compétences →
                      </Link>
                    )}
                  </div>
                )}
              </Panel>

              {/* Résumé des expériences */}
              {experiences.length > 0 && (
                <Panel title={`Expériences (${experiences.length})`}>
                  <div className="space-y-2">
                    {experiences.slice(0, 6).map((exp) => (
                      <div key={exp.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/55 px-4 py-2.5">
                        <BookOpen className="size-4 shrink-0 text-brand" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground">{exp.title}</p>
                          <p className="truncate text-xs text-muted">{exp.organization || TYPE_LABELS[exp.type] || exp.type}</p>
                        </div>
                        {exp.competencies_count !== undefined && exp.competencies_count > 0 && (
                          <span className="shrink-0 rounded-full border border-brand/30 bg-brand-soft px-2 py-0.5 text-[10px] font-semibold text-brand-text">
                            {exp.competencies_count} compétence(s)
                          </span>
                        )}
                      </div>
                    ))}
                    {experiences.length > 6 && (
                      <Link href="/skills/experiences" className="block text-center text-xs text-brand hover:underline">
                        Voir les {experiences.length} expériences →
                      </Link>
                    )}
                  </div>
                </Panel>
              )}

              {/* Résumé des preuves */}
              {evidence.length > 0 && (
                <Panel title={`Preuves (${evidence.length})`}>
                  <div className="flex flex-wrap gap-2">
                    {evidence.slice(0, 8).map((ev) => (
                      <span key={ev.id} className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
                        {ev.title}
                      </span>
                    ))}
                    {evidence.length > 8 && <span className="text-xs text-muted">+{evidence.length - 8}</span>}
                  </div>
                </Panel>
              )}

              {/* Résumé des formations */}
              {educations.length > 0 && (
                <Panel title={`Formations (${educations.length})`}>
                  <div className="space-y-2">
                    {educations.slice(0, 6).map((edu) => (
                      <div key={edu.id} className="flex items-center gap-3 rounded-xl border border-border bg-background/55 px-4 py-2.5">
                        <GraduationCap className="size-4 shrink-0 text-brand" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground">{edu.title}</p>
                        </div>
                        {edu.competencies_count > 0 && (
                          <span className="shrink-0 rounded-full border border-brand/30 bg-brand-soft px-2 py-0.5 text-[10px] font-semibold text-brand-text">
                            {edu.competencies_count} compétence(s)
                          </span>
                        )}
                      </div>
                    ))}
                    {educations.length > 6 && (
                      <Link href="/skills/education" className="block text-center text-xs text-brand hover:underline">
                        Voir les {educations.length} formations →
                      </Link>
                    )}
                  </div>
                </Panel>
              )}

              {/* Benchmark vs JD (collapsible) */}
              <details className="rounded-3xl border border-border bg-surface shadow-sm open:ring-1 open:ring-brand/20">
                <summary className="cursor-pointer select-none px-5 py-4 text-2xl font-semibold text-foreground hover:bg-surface-hover">
                  <span className={`${instrumentSerif.className}`}>Benchmark vs Job Description</span>
                </summary>
                <div className="space-y-3 border-t border-border px-5 pb-5 pt-4">
                  {validated === 0 && (
                    <p className="text-sm text-amber-600 dark:text-amber-400">Valide au moins une compétence d'abord.</p>
                  )}
                  <Input label="Poste cible" value={targetRole} onChange={setTargetRole} placeholder="Ex: Senior Backend Engineer" />
                  <Textarea label="Job Description" value={jdText} onChange={setJdBenchmarkText} placeholder="Colle ici la description du poste..." rows={5} />
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={runBenchmark} disabled={llmBusy || !targetRole.trim() || !jdText.trim()} className="inline-flex items-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2 text-sm font-semibold text-brand-text transition hover:bg-brand/15 disabled:opacity-60">
                      {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                      Lancer le benchmark
                    </button>
                    <button type="button" onClick={generateCvBullets} disabled={llmBusy || !targetRole.trim()} className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60">
                      {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <BookOpen className="size-4" />}
                      CV bullets
                    </button>
                    <button type="button" onClick={generateInterviewQuestions} disabled={llmBusy || !targetRole.trim()} className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60">
                      {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <Brain className="size-4" />}
                      Questions entretien
                    </button>
                    <button type="button" onClick={generateDiscoveryProfile} disabled={llmBusy} className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60">
                      {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                      Profil discovery
                    </button>
                  </div>
                  {benchmarkResult && <pre className="mt-2 rounded-xl border border-border bg-background p-4 text-xs text-muted whitespace-pre-wrap max-h-96 overflow-y-auto">{benchmarkResult}</pre>}
                  {cvBulletsResult && <pre className="mt-2 rounded-xl border border-border bg-background p-4 text-xs text-muted whitespace-pre-wrap max-h-64 overflow-y-auto">{cvBulletsResult}</pre>}
                  {interviewResult && <pre className="mt-2 rounded-xl border border-border bg-background p-4 text-xs text-muted whitespace-pre-wrap max-h-64 overflow-y-auto">{interviewResult}</pre>}
                  {discoveryResult && <pre className="mt-2 rounded-xl border border-border bg-background p-4 text-xs text-muted whitespace-pre-wrap max-h-64 overflow-y-auto">{discoveryResult}</pre>}
                </div>
              </details>

              {/* Générer CV (collapsible) */}
              <details className="rounded-3xl border border-border bg-surface shadow-sm open:ring-1 open:ring-brand/20">
                <summary className="cursor-pointer select-none px-5 py-4 text-2xl font-semibold text-foreground hover:bg-surface-hover">
                  <span className={`${instrumentSerif.className}`}>Générer CV</span>
                </summary>
                <div className="space-y-3 border-t border-border px-5 pb-5 pt-4">
                  <p className="text-sm text-muted">
                    Génère un CV complet à partir de ton portefeuille de compétences, formations et du profil.
                    Les données sont assemblées depuis les compétences validées, les expériences et les formations.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => generateCv("markdown")} disabled={llmBusy} className="inline-flex items-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2 text-sm font-semibold text-brand-text transition hover:bg-brand/15 disabled:opacity-60">
                      {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <BookOpen className="size-4" />}
                      CV Markdown
                    </button>
                    <button type="button" onClick={() => generateCv("json")} disabled={llmBusy} className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60">
                      {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <Award className="size-4" />}
                      CV Data (JSON)
                    </button>
                    {cvResult && (
                      <button type="button" onClick={downloadCv} className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover">
                        Télécharger cv.{cvFormat === "json" ? "json" : "md"}
                      </button>
                    )}
                  </div>
                  {cvResult && (
                    <pre className="mt-2 rounded-xl border border-border bg-background p-4 text-xs text-muted whitespace-pre-wrap max-h-96 overflow-y-auto">
                      {cvResult}
                    </pre>
                  )}
                </div>
              </details>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof Brain; label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border bg-surface/65 p-4 shadow-sm">
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.18em] text-faint">
        {label}
        <Icon className="size-4 text-brand" />
      </div>
      <div className={`${instrumentSerif.className} mt-3 text-3xl text-foreground`}>{value}</div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-border bg-surface p-5 shadow-sm">
      <h2 className={`${instrumentSerif.className} text-3xl text-foreground`}>{title}</h2>
      <div className="mt-4 space-y-3">{children}</div>
    </div>
  );
}

function Input({ label, value, placeholder, onChange }: { label: string; value: string; placeholder?: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <input value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand" />
    </label>
  );
}

function Textarea({ label, value, placeholder, rows = 5, onChange }: { label: string; value: string; placeholder?: string; rows?: number; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <textarea value={value} placeholder={placeholder} rows={rows} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full resize-y rounded-xl border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-faint focus:border-brand" />
    </label>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand">
        <option value="">Non renseigné</option>
        {options.map(([optionValue, labelText]) => (
          <option key={optionValue} value={optionValue}>
            {labelText}
          </option>
        ))}
      </select>
    </label>
  );
}


