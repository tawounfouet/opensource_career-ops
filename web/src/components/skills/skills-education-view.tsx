"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Award,
  Brain,
  Calendar,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileText,
  Filter,
  GraduationCap,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Education = {
  id: number;
  title: string;
  institution: string;
  education_type: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  credential_url: string;
  credential_id: string;
  hours: number | null;
  description: string;
  competencies_count: number;
  education_links: Array<{ id: number; competency: number; competency_label: string; relevance: string }>;
  created_at: string;
};

type Competency = {
  id: number;
  label: string;
  formulation: string;
  category: "knowledge" | "hard_skill" | "soft_skill";
  mastery_level: "beginner" | "junior" | "confirmed" | "expert";
  status: "draft" | "validated" | "rejected" | "archived";
};

const TYPE_LABELS: Record<string, string> = {
  formation: "Formation",
  certification: "Certification",
  rncp: "Titre RNCP",
  professional: "Formation pro",
  mooc: "MOOC",
};

const TYPE_COLORS: Record<string, string> = {
  formation: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  certification: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  rncp: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  professional: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  mooc: "border-cyan-500/30 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
};

const STATUS_LABELS: Record<string, string> = {
  planned: "Planifiee",
  in_progress: "En cours",
  completed: "Terminee",
  expired: "Expiree",
};

const RELEVANCE_LABELS: Record<string, string> = {
  validated: "Validee",
  acquired: "Acquise",
  targeted: "Objectif",
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  const message =
    typeof data === "object" && data !== null && "error" in data
      ? String((data as { error?: unknown }).error || "")
      : "";
  if (!res.ok || message) throw new Error(message || `Request failed (${res.status})`);
  return data as T;
}

export function SkillsEducationView() {
  const [educations, setEducations] = useState<Education[]>([]);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  // LLM extraction
  const [extractText, setExtractText] = useState("");
  const [extractResult, setExtractResult] = useState("");
  const [llmBusy, setLlmBusy] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchJson<{ educations: Education[] }>("/api/skills/educations"),
      fetchJson<{ competencies: Competency[] }>("/api/skills/competencies"),
    ])
      .then(([edu, comp]) => {
        setEducations(edu.educations);
        setCompetencies(comp.competencies);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Chargement impossible"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => {
    let result = educations;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (e) => e.title.toLowerCase().includes(q) || e.institution.toLowerCase().includes(q)
      );
    }
    if (typeFilter) result = result.filter((e) => e.education_type === typeFilter);
    if (statusFilter) result = result.filter((e) => e.status === statusFilter);
    return result;
  }, [educations, searchQuery, typeFilter, statusFilter]);

  const deleteEducation = (id: number) => {
    setBusyId(id);
    fetch(`/api/skills/educations/${id}`, { method: "DELETE" })
      .then((res) => { if (!res.ok) throw new Error("Suppression impossible"); load(); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Suppression impossible"))
      .finally(() => setBusyId(null));
  };

  const extractEducation = () => {
    if (!extractText.trim()) return;
    setLlmBusy(true);
    setError("");
    setExtractResult("");
    fetchJson<{ extracted: unknown[]; created: unknown[]; count: number; error?: string }>("/api/skills/llm/extract-education", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: extractText, persist: true }),
    })
      .then((result) => {
        if (result.error) {
          setExtractResult(`Erreur : ${result.error}`);
        } else {
          setExtractResult(`${result.count} formation(s) extraite(s) et creee(s).`);
          setExtractText("");
          load();
        }
      })
      .catch((e: unknown) => { setExtractResult(`Erreur : ${e instanceof Error ? e.message : "Extraction echouee"}`); })
      .finally(() => setLlmBusy(false));
  };

  const attachCompetency = (eduId: number, compId: number) => {
    setBusyId(eduId);
    fetchJson<Education>(`/api/skills/educations/${eduId}/attach-competency`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ competency_id: compId, relevance: "acquired" }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Lien impossible"))
      .finally(() => setBusyId(null));
  };

  const detachCompetency = (eduId: number, compId: number) => {
    setBusyId(eduId);
    fetchJson<Education>(`/api/skills/educations/${eduId}/detach-competency`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ competency_id: compId }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Detachement impossible"))
      .finally(() => setBusyId(null));
  };

  // KPIs
  const total = educations.length;
  const completed = educations.filter((e) => e.status === "completed").length;
  const inProgress = educations.filter((e) => e.status === "in_progress").length;
  const certifications = educations.filter((e) => e.education_type === "certification").length;
  const rncp = educations.filter((e) => e.education_type === "rncp").length;
  const withoutCompetency = educations.filter((e) => e.competencies_count === 0).length;
  const totalHours = educations.reduce((s, e) => s + (e.hours ?? 0), 0);

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <GraduationCap className="size-3.5 text-brand" />
              Formations · certifications · titres
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Education
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Formations, certifications, titres RNCP et parcours educatifs. Chaque entree peut etre liee a des competences.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/skills" className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover">
              <Plus className="size-4" />
              Ajouter
            </Link>
            <Link href="/skills/list" className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover">
              Compétences
            </Link>
            <Link href="/skills/experiences" className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover">
              Expériences
            </Link>
            <button type="button" onClick={load} disabled={loading} className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-60">
              <RefreshCw className={cn("size-4", loading && "animate-spin")} />
              Rafraichir
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-5 py-6 md:px-10">
        {error && <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300">{error}</div>}

        {/* KPI Row */}
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <KPICard icon={GraduationCap} label="Total" value={String(total)} accent />
          <KPICard icon={CheckCircle2} label="Terminees" value={String(completed)} sub={`${total > 0 ? Math.round((completed / total) * 100) : 0}%`} color="text-emerald-600 dark:text-emerald-400" />
          <KPICard icon={Clock} label="En cours" value={String(inProgress)} color="text-amber-600 dark:text-amber-400" />
          <KPICard icon={ShieldCheck} label="Certifications" value={String(certifications)} color="text-violet-600 dark:text-violet-400" />
          <KPICard icon={Award} label="Titres RNCP" value={String(rncp)} color="text-blue-600 dark:text-blue-400" />
          <KPICard icon={Brain} label="Sans competence" value={String(withoutCompetency)} color={withoutCompetency > 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"} />
        </div>

        {totalHours > 0 && (
          <div className="mb-4 text-xs text-muted">{totalHours}h au total</div>
        )}

        {/* LLM Extraction */}
        <div className="mb-5 rounded-2xl border border-border bg-surface p-4">
          <p className="mb-2 text-xs font-semibold text-foreground">Extraction LLM depuis un texte</p>
          <textarea value={extractText} onChange={(e) => setExtractText(e.target.value)} placeholder="Colle ici un CV, un transcript, ou une description de parcours..." rows={3} className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand" />
          <div className="mt-2 flex items-center gap-3">
            <button type="button" onClick={extractEducation} disabled={llmBusy || !extractText.trim()} className="inline-flex items-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2 text-sm font-semibold text-brand-text transition hover:bg-brand/15 disabled:opacity-60">
              {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Extraire les formations
            </button>
            {extractResult && <p className={cn("text-xs", extractResult.startsWith("Erreur") ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400")}>{extractResult}</p>}
          </div>
        </div>

        {loading ? (
          <div className="grid min-h-96 place-items-center rounded-3xl border border-border bg-surface/50">
            <div className="flex items-center gap-3 text-muted">
              <Loader2 className="size-5 animate-spin text-brand" />
              Chargement...
            </div>
          </div>
        ) : (
          <>
            {/* Filters */}
            <div className="mb-5 flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-surface p-4">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-semibold text-foreground"><Search className="mb-0.5 inline size-3" /> Recherche</label>
                <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Titre, organisme..." className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground"><Filter className="mb-0.5 inline size-3" /> Type</label>
                <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand">
                  <option value="">Tous</option>
                  {Object.entries(TYPE_LABELS).map(([val, label]) => <option key={val} value={val}>{label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground"><Clock className="mb-0.5 inline size-3" /> Statut</label>
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand">
                  <option value="">Tous</option>
                  {Object.entries(STATUS_LABELS).map(([val, label]) => <option key={val} value={val}>{label}</option>)}
                </select>
              </div>
              {(searchQuery || typeFilter || statusFilter) && (
                <button type="button" onClick={() => { setSearchQuery(""); setTypeFilter(""); setStatusFilter(""); }} className="inline-flex items-center gap-1 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-medium text-muted transition hover:bg-surface-hover">
                  <XCircle className="size-3" />
                  Effacer
                </button>
              )}
              <span className="ml-auto text-xs text-muted">{filtered.length} / {total}</span>
            </div>

            {/* Education List */}
            {filtered.length === 0 ? (
              <div className="grid min-h-64 place-items-center rounded-3xl border border-border bg-surface/50">
                <div className="text-center text-muted">
                  <GraduationCap className="mx-auto mb-3 size-8 text-brand/40" />
                  <p className="text-sm">
                    {educations.length === 0 ? "Aucune formation. Ajoute-en une ou utilise l'extraction LLM." : "Aucun resultat pour ces filtres."}
                  </p>
                  {educations.length === 0 && (
                    <Link href="/skills" className="mt-3 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200">
                      <Plus className="size-4" />
                      Ajouter une formation
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map((edu) => (
                  <EducationCard key={edu.id} education={edu} competencies={competencies} busy={busyId === edu.id} onDelete={() => deleteEducation(edu.id)} onAttach={(compId) => attachCompetency(edu.id, compId)} onDetach={(compId) => detachCompetency(edu.id, compId)} />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function KPICard({ icon: Icon, label, value, sub, color, accent }: { icon: typeof Brain; label: string; value: string; sub?: string; color?: string; accent?: boolean }) {
  return (
    <div className={cn("rounded-2xl border bg-surface/65 p-4 shadow-sm", accent ? "border-brand/30 bg-brand/5" : "border-border")}>
      <div className="flex items-center justify-between text-xs uppercase tracking-[0.18em] text-faint">
        {label}
        <Icon className={cn("size-4", color ?? "text-brand")} />
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className={cn(`${instrumentSerif.className} text-3xl`, accent ? "text-brand" : "text-foreground")}>{value}</span>
        {sub && <span className={cn("text-xs font-medium", color ?? "text-muted")}>{sub}</span>}
      </div>
    </div>
  );
}

function EducationCard({ education, competencies, busy, onDelete, onAttach, onDetach }: {
  education: Education;
  competencies: Competency[];
  busy: boolean;
  onDelete: () => void;
  onAttach: (compId: number) => void;
  onDetach: (compId: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [linkCompId, setLinkCompId] = useState<number | null>(null);

  const linkedCompIds = new Set(education.education_links.map((l) => l.competency));
  const unlinked = competencies.filter((c) => !linkedCompIds.has(c.id));

  return (
    <article className="rounded-2xl border border-border bg-surface/40 transition hover:border-brand/30 hover:bg-surface-hover hover:shadow-sm">
      <div className="flex items-center gap-4 px-5 py-4">
        <button type="button" onClick={() => setExpanded(!expanded)} className="flex-1 text-left">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">{education.title}</h3>
            <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-semibold", TYPE_COLORS[education.education_type] ?? "border-border bg-surface text-muted")}>
              {TYPE_LABELS[education.education_type] ?? education.education_type}
            </span>
            <span className={cn("rounded-full border px-2 py-0.5 text-[10px] font-semibold",
              education.status === "completed" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" :
              education.status === "in_progress" ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300" :
              "border-border bg-surface text-muted"
            )}>
              {STATUS_LABELS[education.status] ?? education.status}
            </span>
          </div>
          {education.institution && <p className="mt-1 text-xs text-muted">{education.institution}</p>}
        </button>

        <div className="hidden items-center gap-4 text-xs text-muted lg:flex">
          {education.competencies_count > 0 && (
            <span className="inline-flex items-center gap-1"><Brain className="size-3 text-brand" />{education.competencies_count}</span>
          )}
          {education.hours && (
            <span className="inline-flex items-center gap-1"><Clock className="size-3 text-amber-500" />{education.hours}h</span>
          )}
        </div>

        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button type="button" onClick={onDelete} disabled={busy} className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60">
            {busy ? <Loader2 className="size-3 animate-spin" /> : <XCircle className="size-3" />}
          </button>
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="inline-flex items-center rounded-lg border border-border bg-surface p-1.5 text-muted transition hover:bg-surface-hover"
          >
            <ChevronDown className={cn("size-4 transition-transform", expanded && "rotate-180")} />
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-border px-5 py-4 space-y-4">
          {education.description && <p className="text-xs leading-6 text-muted">{education.description}</p>}

          <div className="flex flex-wrap gap-3 text-xs text-faint">
            {education.start_date && (
              <span className="inline-flex items-center gap-1">
                <Calendar className="size-3" />
                {education.start_date}{education.end_date ? ` → ${education.end_date}` : " → en cours"}
              </span>
            )}
            {education.hours && <span className="inline-flex items-center gap-1"><Clock className="size-3" />{education.hours}h</span>}
            {education.credential_url && (
              <a href={education.credential_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-brand hover:underline">
                <Link2 className="size-3" /> Voir le certificat
              </a>
            )}
            {education.credential_id && <span className="text-muted">ID: {education.credential_id}</span>}
          </div>

          {/* Linked Competencies */}
          <div>
            <p className="text-xs font-semibold text-foreground">Competences liees ({education.education_links.length})</p>
            {education.education_links.length > 0 ? (
              <div className="mt-2 space-y-1.5">
                {education.education_links.map((link) => (
                  <div key={link.id} className="flex items-center justify-between rounded-lg border border-border bg-surface/50 px-3 py-2">
                    <div className="min-w-0">
                      <span className="text-xs font-medium text-foreground">{link.competency_label}</span>
                      <span className="ml-2 rounded-full border border-border bg-surface px-2 py-0.5 text-[10px] font-semibold text-muted">
                        {RELEVANCE_LABELS[link.relevance] ?? link.relevance}
                      </span>
                    </div>
                    <button type="button" onClick={() => onDetach(link.competency)} disabled={busy} className="shrink-0 text-xs text-red-500 hover:underline">
                      Detacher
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted italic">Aucune competence liee</p>
            )}

            {unlinked.length > 0 && (
              <div className="mt-3 flex flex-wrap items-end gap-2 rounded-xl border border-dashed border-border bg-background/30 p-3">
                <label className="block flex-1 min-w-[160px]">
                  <span className="text-xs font-semibold text-foreground">Lier une competence</span>
                  <select value={linkCompId ? String(linkCompId) : ""} onChange={(e) => setLinkCompId(e.target.value ? Number(e.target.value) : null)} className="mt-1 w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-brand">
                    <option value="">Choisir...</option>
                    {unlinked.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                  </select>
                </label>
                <button type="button" onClick={() => { if (linkCompId) { onAttach(linkCompId); setLinkCompId(null); } }} disabled={busy || !linkCompId} className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60">
                  {busy ? <Loader2 className="size-3 animate-spin" /> : <Link2 className="size-3" />}
                  Lier
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
