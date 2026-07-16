"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Award,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  Filter,
  Hammer,
  List,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
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
  evidence_detail?: { id: number; title: string; type: string }[];
  mastery_rationale?: string;
};

type Evidence = {
  id: number;
  title: string;
  type: string;
  description: string;
  source_experience: number | null;
};

type Experience = {
  id: number;
  title: string;
  type: string;
  organization: string;
};

const CATEGORY_LABELS: Record<string, string> = {
  knowledge: "Savoir",
  hard_skill: "Savoir-faire",
  soft_skill: "Savoir-être",
};

const CATEGORY_COLORS: Record<string, string> = {
  knowledge: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300",
  hard_skill: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  soft_skill: "border-violet-500/30 bg-violet-500/10 text-violet-700 dark:text-violet-300",
};

const LEVEL_LABELS: Record<string, string> = {
  beginner: "Débutant",
  junior: "Junior",
  confirmed: "Confirmé",
  expert: "Expert",
};

const LEVEL_ORDER = ["beginner", "junior", "confirmed", "expert"];

const STATUS_LABELS: Record<string, string> = {
  draft: "Brouillon",
  validated: "Validée",
  rejected: "Rejetée",
  archived: "Archivée",
};

const STATUS_COLORS: Record<string, string> = {
  draft: "border-border bg-surface text-muted",
  validated: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  rejected: "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300",
  archived: "border-border bg-surface text-faint",
};

const CONFIDENCE_LABELS: Record<string, string> = {
  low: "Faible",
  medium: "Moyen",
  high: "Élevé",
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

export function SkillsListView() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [competencies, setCompetencies] = useState<Competency[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [evidenceFilter, setEvidenceFilter] = useState<"all" | "with" | "without">("all");

  // Evidence attach
  const [attachCompetencyId, setAttachCompetencyId] = useState<number | null>(null);
  const [attachEvidenceId, setAttachEvidenceId] = useState<number | null>(null);
  const [attachBusy, setAttachBusy] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchJson<Dashboard>("/api/skills/dashboard"),
      fetchJson<{ competencies: Competency[] }>("/api/skills/competencies"),
      fetchJson<{ evidence: Evidence[] }>("/api/skills/evidence"),
      fetchJson<{ experiences: Experience[] }>("/api/skills/experiences"),
    ])
      .then(([dash, comp, ev, exp]) => {
        setDashboard(dash);
        setCompetencies(comp.competencies);
        setEvidence(ev.evidence);
        setExperiences(exp.experiences);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Chargement impossible"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const filtered = useMemo(() => {
    let result = competencies;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.label.toLowerCase().includes(q) ||
          c.formulation.toLowerCase().includes(q)
      );
    }
    if (statusFilter) result = result.filter((c) => c.status === statusFilter);
    if (categoryFilter) result = result.filter((c) => c.category === categoryFilter);
    if (evidenceFilter === "with") result = result.filter((c) => (c.evidence_detail?.length ?? 0) > 0);
    if (evidenceFilter === "without") result = result.filter((c) => (c.evidence_detail?.length ?? 0) === 0);
    return result;
  }, [competencies, searchQuery, statusFilter, categoryFilter, evidenceFilter]);

  const validateCompetency = (competency: Competency) => {
    setBusyId(competency.id);
    setError("");
    fetchJson<Competency>(`/api/skills/competencies/${competency.id}/validate`, { method: "POST" })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Validation impossible"))
      .finally(() => setBusyId(null));
  };

  const rejectCompetency = (competency: Competency) => {
    setBusyId(competency.id);
    setError("");
    fetchJson<Competency>(`/api/skills/competencies/${competency.id}/reject`, { method: "POST" })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Rejet impossible"))
      .finally(() => setBusyId(null));
  };

  const detachEvidence = (competencyId: number, evidenceId: number) => {
    setBusyId(competencyId);
    setError("");
    fetchJson<Competency>(`/api/skills/evidence/detach`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ competency_id: competencyId, evidence_id: evidenceId }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Détachement échoué"))
      .finally(() => setBusyId(null));
  };

  const attachEvidence = () => {
    if (!attachCompetencyId || !attachEvidenceId) return;
    setAttachBusy(true);
    setError("");
    fetchJson<Competency>(`/api/skills/evidence/attach`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ competency_id: attachCompetencyId, evidence_id: attachEvidenceId }),
    })
      .then(() => {
        setAttachCompetencyId(null);
        setAttachEvidenceId(null);
        load();
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Attachement échoué"))
      .finally(() => setAttachBusy(false));
  };

  const validated = dashboard?.by_status.validated ?? 0;
  const draft = dashboard?.by_status.draft ?? 0;
  const rejected = dashboard?.by_status.rejected ?? 0;
  const total = dashboard?.competencies ?? 0;
  const readyToValidate = dashboard?.ready_to_validate ?? 0;
  const withRationale = dashboard?.with_mastery_rationale ?? 0;
  const readinessRate = total > 0 ? Math.round((validated / total) * 100) : 0;

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <List className="size-3.5 text-brand" />
              Suivi · progression · validation
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Compétences
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Vue d&apos;ensemble de ton portefeuille. Filtre, recherche, valide et gère tes compétences.
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
              href="/skills/experiences"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              Expériences
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
          <KPICard icon={Brain} label="Total" value={String(total)} accent />
          <KPICard
            icon={CheckCircle2}
            label="Validées"
            value={String(validated)}
            sub={`${readinessRate}%`}
            color="text-emerald-600 dark:text-emerald-400"
          />
          <KPICard
            icon={Sparkles}
            label="Brouillons"
            value={String(draft)}
            sub={`${readyToValidate} prêtes`}
            color="text-amber-600 dark:text-amber-400"
          />
          <KPICard icon={XCircle} label="Rejetées" value={String(rejected)} color="text-red-500" />
          <KPICard
            icon={ShieldCheck}
            label="Avec preuve"
            value={String(total - (dashboard?.without_evidence ?? 0))}
            sub={`${total > 0 ? Math.round(((total - (dashboard?.without_evidence ?? 0)) / total) * 100) : 0}%`}
            color="text-brand"
          />
          <KPICard
            icon={Target}
            label="Rationale"
            value={String(withRationale)}
            sub={`${total > 0 ? Math.round((withRationale / total) * 100) : 0}%`}
            color="text-violet-600 dark:text-violet-400"
          />
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
                <label className="block text-xs font-semibold text-foreground">
                  <Search className="mb-0.5 inline size-3" /> Recherche
                </label>
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Libellé, formulation..."
                  className="mt-1.5 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground">
                  <Filter className="mb-0.5 inline size-3" /> Statut
                </label>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                >
                  <option value="">Tous</option>
                  <option value="draft">Brouillon</option>
                  <option value="validated">Validée</option>
                  <option value="rejected">Rejetée</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground">
                  <Hammer className="mb-0.5 inline size-3" /> Catégorie
                </label>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                >
                  <option value="">Toutes</option>
                  <option value="knowledge">Savoir</option>
                  <option value="hard_skill">Savoir-faire</option>
                  <option value="soft_skill">Savoir-être</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-foreground">
                  <Award className="mb-0.5 inline size-3" /> Preuve
                </label>
                <select
                  value={evidenceFilter}
                  onChange={(e) => setEvidenceFilter(e.target.value as "all" | "with" | "without")}
                  className="mt-1.5 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
                >
                  <option value="all">Toutes</option>
                  <option value="with">Avec preuve</option>
                  <option value="without">Sans preuve</option>
                </select>
              </div>
              {(searchQuery || statusFilter || categoryFilter || evidenceFilter !== "all") && (
                <button
                  type="button"
                  onClick={() => { setSearchQuery(""); setStatusFilter(""); setCategoryFilter(""); setEvidenceFilter("all"); }}
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

            {/* Competency Table */}
            {filtered.length === 0 ? (
              <div className="grid min-h-64 place-items-center rounded-3xl border border-border bg-surface/50">
                <div className="text-center text-muted">
                  <Brain className="mx-auto mb-3 size-8 text-brand/40" />
                  <p className="text-sm">
                    {competencies.length === 0
                      ? "Aucune compétence. Commence par en ajouter une."
                      : "Aucun résultat pour ces filtres."}
                  </p>
                  {competencies.length === 0 && (
                    <Link href="/skills" className="mt-3 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200">
                      <Plus className="size-4" />
                      Ajouter une compétence
                    </Link>
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {/* Table header */}
                <div className="hidden rounded-2xl border border-border bg-surface px-5 py-3 text-xs font-semibold uppercase tracking-wider text-faint lg:grid lg:grid-cols-[1fr_140px_120px_100px_80px_160px]">
                  <span>Compétence</span>
                  <span>Catégorie</span>
                  <span>Niveau</span>
                  <span>Statut</span>
                  <span>Preuves</span>
                  <span className="text-right">Actions</span>
                </div>

                {filtered.map((competency) => (
                  <CompetencyTableRow
                    key={competency.id}
                    competency={competency}
                    busy={busyId === competency.id}
                    onValidate={() => validateCompetency(competency)}
                    onReject={() => rejectCompetency(competency)}
                    onDetachEvidence={(evId) => detachEvidence(competency.id, evId)}
                    evidence={evidence}
                    attachCompetencyId={attachCompetencyId}
                    setAttachCompetencyId={setAttachCompetencyId}
                    attachEvidenceId={attachEvidenceId}
                    setAttachEvidenceId={setAttachEvidenceId}
                    onAttachEvidence={attachEvidence}
                    attachBusy={attachBusy}
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

function CompetencyTableRow({
  competency,
  busy,
  onValidate,
  onReject,
  onDetachEvidence,
  evidence,
  attachCompetencyId,
  setAttachCompetencyId,
  attachEvidenceId,
  setAttachEvidenceId,
  onAttachEvidence,
  attachBusy,
}: {
  competency: Competency;
  busy: boolean;
  onValidate: () => void;
  onReject: () => void;
  onDetachEvidence: (evidenceId: number) => void;
  evidence: Evidence[];
  attachCompetencyId: number | null;
  setAttachCompetencyId: (id: number | null) => void;
  attachEvidenceId: number | null;
  setAttachEvidenceId: (id: number | null) => void;
  onAttachEvidence: () => void;
  attachBusy: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const evidenceCount = competency.evidence_detail?.length ?? 0;

  return (
    <article className="rounded-2xl border border-border bg-surface/40 transition hover:border-brand/30 hover:bg-surface-hover hover:shadow-sm">
      {/* Main row */}
      <div
        className="grid cursor-pointer items-center gap-3 px-5 py-4 lg:grid-cols-[1fr_140px_120px_100px_80px_160px]"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Label + formulation */}
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-foreground">{competency.label}</h3>
          <p className="mt-0.5 truncate text-xs text-muted">{competency.formulation}</p>
        </div>

        {/* Category */}
        <span className={cn("w-fit rounded-full border px-2.5 py-1 text-xs font-semibold", CATEGORY_COLORS[competency.category] ?? "border-border bg-surface text-muted")}>
          {CATEGORY_LABELS[competency.category] ?? competency.category}
        </span>

        {/* Mastery level */}
        <span className="text-xs font-medium text-foreground">
          {LEVEL_LABELS[competency.mastery_level] ?? competency.mastery_level}
        </span>

        {/* Status */}
        <span className={cn("w-fit rounded-full border px-2.5 py-1 text-xs font-semibold", STATUS_COLORS[competency.status] ?? "border-border bg-surface text-muted")}>
          {STATUS_LABELS[competency.status] ?? competency.status}
        </span>

        {/* Evidence count */}
        <span className={cn("text-xs font-medium", evidenceCount > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-400")}>
          {evidenceCount}
        </span>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2" onClick={(e) => e.stopPropagation()}>
          {competency.status !== "validated" && (
            <button
              type="button"
              onClick={onValidate}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-brand/30 bg-brand-soft px-2.5 py-1.5 text-xs font-medium text-brand-text transition hover:bg-brand/15 disabled:opacity-60"
            >
              {busy ? <Loader2 className="size-3 animate-spin" /> : <CheckCircle2 className="size-3" />}
              Valider
            </button>
          )}
          {competency.status !== "rejected" && (
            <button
              type="button"
              onClick={onReject}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60"
            >
              <XCircle className="size-3" />
            </button>
          )}
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
        <div className="border-t border-border px-5 py-4 space-y-3">
          <p className="text-xs leading-6 text-muted">{competency.formulation}</p>

          {competency.mastery_rationale && (
            <div className="rounded-xl border border-border bg-background/50 p-3">
              <p className="text-xs font-semibold text-foreground">Rationale de maîtrise</p>
              <p className="mt-1 text-xs text-muted">{competency.mastery_rationale}</p>
            </div>
          )}

          {/* Evidence list */}
          <div>
            <p className="text-xs font-semibold text-foreground">Preuves ({evidenceCount})</p>
            {evidenceCount > 0 ? (
              <div className="mt-2 space-y-1.5">
                {competency.evidence_detail?.map((ev) => (
                  <div key={ev.id} className="flex items-center justify-between rounded-lg border border-border bg-surface/50 px-3 py-2">
                    <div>
                      <span className="text-xs font-medium text-foreground">{ev.title}</span>
                      <span className="ml-2 text-xs text-muted">({ev.type})</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => onDetachEvidence(ev.id)}
                      className="text-xs text-red-500 hover:underline"
                    >
                      Détacher
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted italic">Aucune preuve attachée</p>
            )}
          </div>

          {/* Attach evidence */}
          {evidence.length > 0 && (
            <div className="flex flex-wrap items-end gap-2 rounded-xl border border-dashed border-border bg-background/30 p-3">
              <label className="block">
                <span className="text-xs font-semibold text-foreground">Attacher une preuve</span>
                <select
                  value={attachEvidenceId ? String(attachEvidenceId) : ""}
                  onChange={(e) => setAttachEvidenceId(e.target.value ? Number(e.target.value) : null)}
                  className="mt-1 w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs text-foreground outline-none focus:border-brand"
                >
                  <option value="">Choisir...</option>
                  {evidence.map((ev) => (
                    <option key={ev.id} value={ev.id}>
                      {ev.title}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => { setAttachCompetencyId(competency.id); onAttachEvidence(); }}
                disabled={attachBusy || !attachEvidenceId}
                className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs font-medium text-foreground transition hover:bg-surface-hover disabled:opacity-60"
              >
                {attachBusy ? <Loader2 className="size-3 animate-spin" /> : <Plus className="size-3" />}
                Attacher
              </button>
            </div>
          )}

          {/* Meta info */}
          <div className="flex flex-wrap gap-3 text-xs text-faint">
            <span>Confiance: {CONFIDENCE_LABELS[competency.confidence] ?? competency.confidence}</span>
            {competency.experience_ids && competency.experience_ids.length > 0 && (
              <span>Expériences: {competency.experience_ids.length}</span>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
