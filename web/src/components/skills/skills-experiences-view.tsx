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
  Hammer,
  Link2,
  Loader2,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Wrench,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Dashboard = {
  experiences: number;
  competencies: number;
  evidence: number;
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  without_evidence: number;
  with_evidence?: number;
  with_mastery_rationale?: number;
  ready_to_validate?: number;
};

type Experience = {
  id: number;
  title: string;
  type: string;
  organization: string;
  description: string;
  start_date: string | null;
  end_date: string | null;
  location: string;
  deliverables: string[];
  outcomes: string[];
  tools: string[];
  missions: string[];
  responsibilities: string[];
  people_context: string;
  competencies_count?: number;
  evidence_count?: number;
  created_at: string;
};

type Competency = {
  id: number;
  label: string;
  formulation: string;
  category: "knowledge" | "hard_skill" | "soft_skill";
  mastery_level: "beginner" | "junior" | "confirmed" | "expert";
  status: "draft" | "validated" | "rejected" | "archived";
  experience_ids?: number[];
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

const TYPE_COLORS: Record<string, string> = {
  professional: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  project: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  education: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
  volunteer: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
  personal: "border-pink-500/30 bg-pink-500/10 text-pink-700 dark:text-pink-300",
  travel: "border-cyan-500/30 bg-cyan-500/10 text-cyan-700 dark:text-cyan-300",
  cultural: "border-orange-500/30 bg-orange-500/10 text-orange-700 dark:text-orange-300",
  other: "border-border bg-surface text-muted",
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

export function SkillsExperiencesView() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [extractText, setExtractText] = useState("");
  const [llmBusy, setLlmBusy] = useState(false);
  const [extractResult, setExtractResult] = useState("");

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("");
  const [hasDeliverables, setHasDeliverables] = useState<"all" | "yes" | "no">("all");
  const [hasTools, setHasTools] = useState<"all" | "yes" | "no">("all");

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchJson<Dashboard>("/api/skills/dashboard"),
      fetchJson<{ experiences: Experience[] }>("/api/skills/experiences"),
      fetchJson<{ competencies: Competency[] }>("/api/skills/competencies"),
    ])
      .then(([dash, exp, comp]) => {
        setDashboard(dash);
        setExperiences(exp.experiences);
        setCompetencies(comp.competencies);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Chargement impossible"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    let result = experiences;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (e) =>
          e.title.toLowerCase().includes(q) ||
          e.organization.toLowerCase().includes(q) ||
          e.description.toLowerCase().includes(q)
      );
    }
    if (typeFilter) result = result.filter((e) => e.type === typeFilter);
    if (hasDeliverables === "yes") result = result.filter((e) => e.deliverables.length > 0);
    if (hasDeliverables === "no") result = result.filter((e) => e.deliverables.length === 0);
    if (hasTools === "yes") result = result.filter((e) => e.tools.length > 0);
    if (hasTools === "no") result = result.filter((e) => e.tools.length === 0);
    return result;
  }, [experiences, searchQuery, typeFilter, hasDeliverables, hasTools]);

  const deleteExperience = (id: number) => {
    setBusyId(id);
    setError("");
    fetch(`/api/skills/experiences/${id}`, { method: "DELETE" })
      .then((res) => {
        if (!res.ok) throw new Error("Suppression impossible");
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Suppression impossible"))
      .finally(() => setBusyId(null));
  };

  const extractExperience = () => {
    if (!extractText.trim()) return;
    setLlmBusy(true);
    setError("");
    setExtractResult("");
    fetchJson<{ extracted: unknown[]; created: unknown[]; count: number; error?: string }>("/api/skills/llm/extract-experience", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: extractText, persist: true }),
    })
      .then((result) => {
        if (result.error) {
          setExtractResult(`Erreur : ${result.error}`);
        } else {
          setExtractResult(`${result.count} experience(s) extraite(s) et creee(s).`);
          setExtractText("");
          load();
        }
      })
      .catch((e: unknown) => { setExtractResult(`Erreur : ${e instanceof Error ? e.message : "Extraction echouee"}`); })
      .finally(() => setLlmBusy(false));
  };

  const linkCompetencyToExperience = (competencyId: number, experienceId: number) => {
    setBusyId(experienceId);
    setError("");
    const comp = competencies.find((c) => c.id === competencyId);
    if (!comp) { setBusyId(null); return; }
    const currentExpIds = comp.experience_ids ?? [];
    if (currentExpIds.includes(experienceId)) { setBusyId(null); return; }
    fetchJson<Competency>(`/api/skills/competencies/${competencyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ experience_ids: [...currentExpIds, experienceId] }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Lien impossible"))
      .finally(() => setBusyId(null));
  };

  const unlinkCompetencyFromExperience = (competencyId: number, experienceId: number) => {
    setBusyId(experienceId);
    setError("");
    const comp = competencies.find((c) => c.id === competencyId);
    if (!comp) { setBusyId(null); return; }
    const currentExpIds = comp.experience_ids ?? [];
    fetchJson<Competency>(`/api/skills/competencies/${competencyId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ experience_ids: currentExpIds.filter((id) => id !== experienceId) }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Détachement impossible"))
      .finally(() => setBusyId(null));
  };

  // KPIs
  const total = dashboard?.experiences ?? 0;
  const totalCompetencies = dashboard?.competencies ?? 0;
  const totalEvidence = dashboard?.evidence ?? 0;

  // Group by type
  const byType = useMemo(() => {
    const map: Record<string, number> = {};
    experiences.forEach((e) => {
      map[e.type] = (map[e.type] || 0) + 1;
    });
    return map;
  }, [experiences]);

  const withDeliverables = experiences.filter((e) => e.deliverables.length > 0).length;
  const withOutcomes = experiences.filter((e) => e.outcomes.length > 0).length;
  const withTools = experiences.filter((e) => e.tools.length > 0).length;
  const withOrg = experiences.filter((e) => e.organization.trim()).length;
  const avgTools = total > 0 ? (experiences.reduce((s, e) => s + e.tools.length, 0) / total).toFixed(1) : "0";
  const totalLinkedCompetencies = experiences.reduce((s, e) => s + (e.competencies_count ?? 0), 0);

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <FileText className="size-3.5 text-brand" />
              Sources · contexte · preuves
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Expériences
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Vue d&apos;ensemble de tes sources de compétences. Chaque expérience alimente l&apos;extraction et la validation.
            </p>
          </div>
          <div className="flex gap-2">
            <Link
              href="/skills"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              <Plus className="size-4" />
              Ajouter
            </Link>
            <Link
              href="/skills/list"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              Compétences
            </Link>
            <Link
              href="/skills/education"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
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
        {error && (
          <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        {/* KPI Row */}
        <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <KPICard icon={FileText} label="Total" value={String(total)} accent />
          <KPICard
            icon={Link2}
            label="Compétences liées"
            value={String(totalLinkedCompetencies)}
            sub={`/${totalCompetencies}`}
            color="text-brand"
          />
          <KPICard
            icon={Award}
            label="Livrables"
            value={String(withDeliverables)}
            sub={`${total > 0 ? Math.round((withDeliverables / total) * 100) : 0}%`}
            color="text-emerald-600 dark:text-emerald-400"
          />
          <KPICard
            icon={Target}
            label="Résultats"
            value={String(withOutcomes)}
            sub={`${total > 0 ? Math.round((withOutcomes / total) * 100) : 0}%`}
            color="text-violet-600 dark:text-violet-400"
          />
          <KPICard
            icon={Wrench}
            label="Outils"
            value={String(withTools)}
            sub={`moy. ${avgTools}/exp`}
            color="text-amber-600 dark:text-amber-400"
          />
          <KPICard
            icon={Brain}
            label="Preuves"
            value={String(totalEvidence)}
            color="text-blue-600 dark:text-blue-400"
          />
        </div>

        {/* Type breakdown */}
        {total > 0 && (
          <div className="mb-5 flex flex-wrap gap-2">
            {Object.entries(byType)
              .sort((a, b) => b[1] - a[1])
              .map(([type, count]) => (
                <span
                  key={type}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold",
                    TYPE_COLORS[type] ?? "border-border bg-surface text-muted"
                  )}
                >
                  {TYPE_LABELS[type] ?? type}
                  <span className="opacity-60">{count}</span>
                </span>
              ))}
          </div>
        )}

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
                <label className="block text-xs font-semibold text-foreground">
                  <Search className="mb-0.5 inline size-3" /> Recherche
                </label>
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Titre, organisation, description..."
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground">
                  <Filter className="mb-0.5 inline size-3" /> Type
                </label>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                >
                  <option value="">Tous</option>
                  {Object.entries(TYPE_LABELS).map(([val, label]) => (
                    <option key={val} value={val}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground">
                  <Award className="mb-0.5 inline size-3" /> Livrables
                </label>
                <select
                  value={hasDeliverables}
                  onChange={(e) => setHasDeliverables(e.target.value as "all" | "yes" | "no")}
                  className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                >
                  <option value="all">Toutes</option>
                  <option value="yes">Avec livrables</option>
                  <option value="no">Sans livrables</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground">
                  <Wrench className="mb-0.5 inline size-3" /> Outils
                </label>
                <select
                  value={hasTools}
                  onChange={(e) => setHasTools(e.target.value as "all" | "yes" | "no")}
                  className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                >
                  <option value="all">Toutes</option>
                  <option value="yes">Avec outils</option>
                  <option value="no">Sans outils</option>
                </select>
              </div>
              {(searchQuery || typeFilter || hasDeliverables !== "all" || hasTools !== "all") && (
                <button
                  type="button"
                  onClick={() => { setSearchQuery(""); setTypeFilter(""); setHasDeliverables("all"); setHasTools("all"); }}
                  className="inline-flex items-center gap-1 rounded-xl border border-border bg-surface px-3 py-2 text-xs font-medium text-muted transition hover:bg-surface-hover"
                >
                  <XCircle className="size-3" />
                  Effacer
                </button>
              )}
              <span className="ml-auto text-xs text-muted">
                {filtered.length} / {total}
              </span>
            </div>

            {/* LLM Extraction */}
            <div className="mb-5 rounded-2xl border border-border bg-surface p-4">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Sparkles className="size-4 text-brand" />
                Extraction LLM depuis un texte
              </h3>
              <p className="mb-3 text-xs text-muted">
                Colle ici un CV, un transcript, ou une description de parcours...
              </p>
              <textarea
                value={extractText}
                onChange={(e) => setExtractText(e.target.value)}
                placeholder="Colle ici un CV, un transcript, ou une description de parcours..."
                rows={6}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
              />
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  onClick={extractExperience}
                  disabled={llmBusy || !extractText.trim()}
                  className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-medium text-white transition hover:bg-brand/90 disabled:opacity-60"
                >
                  {llmBusy ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                  Extraire les experiences
                </button>
                {extractResult && (
                  <span className={cn("text-sm", extractResult.startsWith("Erreur") ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400")}>
                    {extractResult}
                  </span>
                )}
              </div>
            </div>

            {/* Experience List */}
            {filtered.length === 0 ? (
              <div className="grid min-h-64 place-items-center rounded-3xl border border-border bg-surface/50">
                <div className="text-center text-muted">
                  <FileText className="mx-auto mb-3 size-8 text-brand/40" />
                  <p className="text-sm">
                    {experiences.length === 0
                      ? "Aucune expérience. Commence par en ajouter une."
                      : "Aucun résultat pour ces filtres."}
                  </p>
                  {experiences.length === 0 && (
                    <Link href="/skills" className="mt-3 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200">
                      <Plus className="size-4" />
                      Ajouter une expérience
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {filtered.map((experience) => (
                  <ExperienceCard
                    key={experience.id}
                    experience={experience}
                    competencies={competencies}
                    busy={busyId === experience.id}
                    onDelete={() => deleteExperience(experience.id)}
                    onLink={(compId) => linkCompetencyToExperience(compId, experience.id)}
                    onUnlink={(compId) => unlinkCompetencyFromExperience(compId, experience.id)}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function KPICard({
  icon: Icon,
  label,
  value,
  sub,
  color,
  accent,
}: {
  icon: typeof Brain;
  label: string;
  value: string;
  sub?: string;
  color?: string;
  accent?: boolean;
}) {
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

function ExperienceCard({
  experience,
  competencies,
  busy,
  onDelete,
  onLink,
  onUnlink,
}: {
  experience: Experience;
  competencies: Competency[];
  busy: boolean;
  onDelete: () => void;
  onLink: (competencyId: number) => void;
  onUnlink: (competencyId: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [linkCompetencyId, setLinkCompetencyId] = useState<number | null>(null);
  const deliverablesCount = experience.deliverables.length;
  const outcomesCount = experience.outcomes.length;
  const toolsCount = experience.tools.length;
  const compCount = experience.competencies_count ?? 0;

  // Competencies linked to this experience
  const linkedCompetencies = competencies.filter((c) => (c.experience_ids ?? []).includes(experience.id));
  // Competencies not yet linked
  const unlinkedCompetencies = competencies.filter((c) => !(c.experience_ids ?? []).includes(experience.id));

  return (
    <article className="rounded-2xl border border-border bg-surface/40 transition hover:border-brand/30 hover:bg-surface-hover hover:shadow-sm">
      {/* Main row */}
      <div className="flex items-center gap-4 px-5 py-4">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex-1 text-left"
        >
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">{experience.title}</h3>
            <span className={cn("rounded-full border px-2.5 py-0.5 text-xs font-semibold", TYPE_COLORS[experience.type] ?? "border-border bg-surface text-muted")}>
              {TYPE_LABELS[experience.type] ?? experience.type}
            </span>
          </div>
          {experience.organization && (
            <p className="mt-1 text-xs text-muted">{experience.organization}</p>
          )}
        </button>

        {/* Mini stats */}
        <div className="hidden items-center gap-4 text-xs text-muted lg:flex">
          {compCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Brain className="size-3 text-brand" />
              {compCount}
            </span>
          )}
          {deliverablesCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Award className="size-3 text-emerald-500" />
              {deliverablesCount}
            </span>
          )}
          {outcomesCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Target className="size-3 text-violet-500" />
              {outcomesCount}
            </span>
          )}
          {toolsCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Wrench className="size-3 text-amber-500" />
              {toolsCount}
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <button
            type="button"
            onClick={() => onDelete()}
            disabled={busy}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60"
          >
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

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-border px-5 py-4 space-y-4">
          {experience.description && (
            <p className="text-xs leading-6 text-muted">{experience.description}</p>
          )}

          {/* Meta */}
          <div className="flex flex-wrap gap-3 text-xs text-faint">
            {experience.start_date && (
              <span className="inline-flex items-center gap-1">
                <Calendar className="size-3" />
                {experience.start_date}
                {experience.end_date ? ` → ${experience.end_date}` : " → présent"}
              </span>
            )}
            {experience.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="size-3" />
                {experience.location}
              </span>
            )}
            {experience.people_context && (
              <span className="inline-flex items-center gap-1">
                <FileText className="size-3" />
                Équipe: {experience.people_context}
              </span>
            )}
          </div>

          {/* Deliverables */}
          {deliverablesCount > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground">Livrables ({deliverablesCount})</p>
              <ul className="mt-1 space-y-0.5">
                {experience.deliverables.map((d, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-muted">
                    <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-emerald-500" />
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Outcomes */}
          {outcomesCount > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground">Résultats ({outcomesCount})</p>
              <ul className="mt-1 space-y-0.5">
                {experience.outcomes.map((o, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-muted">
                    <Target className="mt-0.5 size-3 shrink-0 text-violet-500" />
                    {o}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Tools */}
          {toolsCount > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground">Outils ({toolsCount})</p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {experience.tools.map((t, i) => (
                  <span key={i} className="rounded-full border border-border bg-surface px-2.5 py-0.5 text-xs text-muted">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Missions */}
          {experience.missions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground">Missions ({experience.missions.length})</p>
              <ul className="mt-1 space-y-0.5">
                {experience.missions.map((m, i) => (
                  <li key={i} className="text-xs text-muted">• {m}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Responsibilities */}
          {experience.responsibilities.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-foreground">Responsabilités ({experience.responsibilities.length})</p>
              <ul className="mt-1 space-y-0.5">
                {experience.responsibilities.map((r, i) => (
                  <li key={i} className="text-xs text-muted">• {r}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Linked Competencies */}
          <div>
            <p className="text-xs font-semibold text-foreground">Compétences liées ({linkedCompetencies.length})</p>
            {linkedCompetencies.length > 0 ? (
              <div className="mt-2 space-y-1.5">
                {linkedCompetencies.map((comp) => (
                  <div key={comp.id} className="flex items-center justify-between rounded-lg border border-border bg-surface/50 px-3 py-2">
                    <div className="min-w-0">
                      <span className="text-xs font-medium text-foreground">{comp.label}</span>
                      <span className={cn("ml-2 rounded-full border px-2 py-0.5 text-[10px] font-semibold",
                        comp.status === "validated" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "border-border bg-surface text-muted"
                      )}>
                        {comp.status}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => onUnlink(comp.id)}
                      disabled={busy}
                      className="shrink-0 text-xs text-red-500 hover:underline"
                    >
                      Détacher
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted italic">Aucune compétence liée</p>
            )}

            {/* Link competency */}
            {unlinkedCompetencies.length > 0 && (
              <div className="mt-3 flex flex-wrap items-end gap-2 rounded-xl border border-dashed border-border bg-background/30 p-3">
                <label className="block flex-1 min-w-[160px]">
                  <span className="text-xs font-semibold text-foreground">Lier une compétence</span>
                  <select
                    value={linkCompetencyId ? String(linkCompetencyId) : ""}
                    onChange={(e) => setLinkCompetencyId(e.target.value ? Number(e.target.value) : null)}
                    className="mt-1 w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-brand"
                  >
                    <option value="">Choisir...</option>
                    {unlinkedCompetencies.map((comp) => (
                      <option key={comp.id} value={comp.id}>
                        {comp.label}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() => { if (linkCompetencyId) { onLink(linkCompetencyId); setLinkCompetencyId(null); } }}
                  disabled={busy || !linkCompetencyId}
                  className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60"
                >
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
