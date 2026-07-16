"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";
import {
  ArrowUpRight,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Loader2,
  Moon,
  Play,
  RefreshCw,
  Send,
  SkipForward,
  SlidersHorizontal,
  Star,
  TimerReset,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Decision = "pending" | "evaluate" | "skip" | "blacklist_company" | "save_for_later" | "already_applied";

type DiscoveryJob = {
  id: number;
  title: string;
  company: string;
  location: string;
  remote_type: string;
  contract_type: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  apply_url: string;
  source_url: string;
  all_sources: string[];
  posted_at: string | null;
  language: string;
  market: string;
};

type DiscoveryRanking = {
  score: number;
  freshness_score: number;
  title_score: number;
  keyword_score: number;
  location_score: number;
  remote_score: number;
  contract_score: number;
  salary_score: number;
  company_score: number;
  negative_penalty: number;
  rejected: boolean;
  reject_reason: string;
  explanations: string[];
  rank: number;
};

type DigestItem = {
  id: number;
  rank: number;
  decision: Decision;
  decision_note: string;
  exported_to_pipeline_at: string | null;
  job: DiscoveryJob;
  ranking: DiscoveryRanking | null;
};

type Digest = {
  id?: number;
  date: string;
  status?: string;
  total_candidates?: number;
  items_count?: number;
  empty?: boolean;
  items: DigestItem[];
};

const DECISION_META: Record<Decision, { label: string; tone: string }> = {
  pending: { label: "À trier", tone: "border-border bg-surface text-muted" },
  evaluate: { label: "À évaluer", tone: "border-brand/30 bg-brand-soft text-brand-text" },
  skip: { label: "Ignorée", tone: "border-zinc-400/30 bg-zinc-500/10 text-muted" },
  blacklist_company: { label: "Entreprise bloquée", tone: "border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-300" },
  save_for_later: { label: "Plus tard", tone: "border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300" },
  already_applied: { label: "Déjà postulé", tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" },
};

function formatDate(value: string | null): string {
  if (!value) return "date inconnue";
  try {
    return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" }).format(new Date(`${value}T00:00:00`));
  } catch {
    return value;
  }
}

function formatSalary(job: DiscoveryJob): string {
  if (!job.salary_min && !job.salary_max) return "Salaire non indiqué";
  const currency = job.salary_currency || "EUR";
  const fmt = (n: number) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n);
  if (job.salary_min && job.salary_max) return `${fmt(job.salary_min)}-${fmt(job.salary_max)} ${currency}`;
  return `${fmt(job.salary_min || job.salary_max || 0)} ${currency}`;
}

function scoreTone(score: number): string {
  if (score >= 55) return "text-emerald-700 dark:text-emerald-300";
  if (score >= 42) return "text-brand-text";
  if (score >= 30) return "text-amber-700 dark:text-amber-300";
  return "text-muted";
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  const message = typeof data === "object" && data !== null && "error" in data ? String((data as { error?: unknown }).error || "") : "";
  if (!res.ok) throw new Error(message || `Request failed (${res.status})`);
  return data as T;
}

function scoreParts(item: DigestItem) {
  const r = item.ranking;
  if (!r) return [];
  return [
    ["Titre", r.title_score],
    ["Mots-clés", r.keyword_score],
    ["Fraîcheur", r.freshness_score],
    ["Lieu", r.location_score],
    ["Remote", r.remote_score],
    ["Contrat", r.contract_score],
  ].filter(([, value]) => Number(value) !== 0) as [string, number][];
}

export function DiscoveryMorningView() {
  const [digest, setDigest] = useState<Digest | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [isPending, startTransition] = useTransition();

  const load = () => {
    setLoading(true);
    setError("");
    fetchJson<Digest>("/api/discovery/digest/today")
      .then(setDigest)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Impossible de charger le digest"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const stats = useMemo(() => {
    const items = digest?.items ?? [];
    return {
      total: items.length,
      evaluate: items.filter((i) => i.decision === "evaluate").length,
      exported: items.filter((i) => i.exported_to_pipeline_at).length,
      avg: items.length ? Math.round(items.reduce((s, i) => s + (i.ranking?.score ?? 0), 0) / items.length) : 0,
    };
  }, [digest]);

  const decide = (item: DigestItem, decision: Decision) => {
    setBusyId(item.id);
    fetchJson<{ ok: boolean; decision: Decision }>(`/api/discovery/items/${item.id}/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Décision impossible"))
      .finally(() => setBusyId(null));
  };

  const exportItem = (item: DigestItem) => {
    setBusyId(item.id);
    fetchJson<{ ok: boolean; added?: boolean }>(`/api/discovery/items/${item.id}/export-pipeline`, { method: "POST" })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Export impossible"))
      .finally(() => setBusyId(null));
  };

  const runDiscovery = () => {
    setRunning(true);
    setError("");
    fetchJson<{ digest?: { items?: number } }>("/api/discovery/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: "default" }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Run discovery impossible"))
      .finally(() => setRunning(false));
  };

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-32 -top-40 -z-10 h-96 w-96 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <Moon className="size-3.5 text-brand" />
              Collecte nocturne · revue matinale
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Offres du jour
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Une short-list déterministe issue des ATS et jobboards activés. Tu décides : évaluer, ignorer, garder pour plus tard ou exporter vers le pipeline.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link
              href="/discovery/profile"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              <SlidersHorizontal className="size-4" />
              Critères
            </Link>
            <button
              type="button"
              onClick={() => startTransition(load)}
              disabled={loading || isPending}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-60"
            >
              <RefreshCw className={cn("size-4", (loading || isPending) && "animate-spin")} />
              Rafraîchir
            </button>
            <button
              type="button"
              onClick={runDiscovery}
              disabled={running}
              className="inline-flex items-center gap-2 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground shadow-sm transition hover:bg-brand-200 disabled:opacity-60"
            >
              {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
              Run manuel
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

        <div className="mb-6 grid gap-3 md:grid-cols-4">
          <Stat icon={CalendarDays} label="Digest" value={digest?.date ?? "—"} />
          <Stat icon={BriefcaseBusiness} label="Offres" value={String(stats.total)} />
          <Stat icon={Star} label="Score moyen" value={stats.avg ? `${stats.avg}/100` : "—"} />
          <Stat icon={Send} label="Exportées" value={`${stats.exported}/${stats.evaluate}`} />
        </div>

        {loading ? (
          <div className="grid min-h-80 place-items-center rounded-3xl border border-border bg-surface/50">
            <div className="flex items-center gap-3 text-muted">
              <Loader2 className="size-5 animate-spin text-brand" />
              Chargement du digest...
            </div>
          </div>
        ) : !digest || digest.empty || digest.items.length === 0 ? (
          <EmptyState runDiscovery={runDiscovery} running={running} />
        ) : (
          <div className="grid gap-4">
            {digest.items.map((item) => (
              <JobRow
                key={item.id}
                item={item}
                busy={busyId === item.id}
                onDecision={(decision) => decide(item, decision)}
                onExport={() => exportItem(item)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: typeof BriefcaseBusiness; label: string; value: string }) {
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

function EmptyState({ runDiscovery, running }: { runDiscovery: () => void; running: boolean }) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-border bg-surface p-10 text-center shadow-sm">
      <div className="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-brand/50 to-transparent" />
      <TimerReset className="mx-auto size-10 text-brand" />
      <h2 className={`${instrumentSerif.className} mt-4 text-3xl text-foreground`}>Aucun digest prêt pour ce matin</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted">
        Lance un run manuel si Django est démarré, ou configure le cron nocturne pour préparer la short-list automatiquement.
      </p>
      <button
        type="button"
        onClick={runDiscovery}
        disabled={running}
        className="mt-6 inline-flex items-center gap-2 rounded-full bg-brand px-5 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60"
      >
        {running ? <Loader2 className="size-4 animate-spin" /> : <Play className="size-4" />}
        Préparer maintenant
      </button>
    </div>
  );
}

function JobRow({ item, busy, onDecision, onExport }: { item: DigestItem; busy: boolean; onDecision: (d: Decision) => void; onExport: () => void }) {
  const job = item.job;
  const ranking = item.ranking;
  const meta = DECISION_META[item.decision];
  const url = job.apply_url || job.source_url;
  const parts = scoreParts(item);

  return (
    <article className="group overflow-hidden rounded-2xl border border-border bg-surface/80 shadow-sm transition hover:-translate-y-0.5 hover:border-brand/30">
      <div className="grid gap-0 lg:grid-cols-[92px_1fr_300px]">
        <div className="flex border-b border-border bg-surface-hover/50 p-4 lg:flex-col lg:items-center lg:justify-center lg:border-b-0 lg:border-r">
          <span className="text-xs font-semibold uppercase tracking-[0.18em] text-faint">Rank</span>
          <span className={`${instrumentSerif.className} ml-3 text-4xl text-landing lg:ml-0 lg:mt-2`}>{item.rank}</span>
        </div>

        <div className="min-w-0 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <a href={url} target="_blank" rel="noopener noreferrer" className="group/title inline-flex max-w-full items-start gap-2">
                <h2 className={`${instrumentSerif.className} truncate text-2xl leading-tight text-foreground group-hover/title:text-brand md:text-3xl`}>
                  {job.title}
                </h2>
                <ArrowUpRight className="mt-1 size-4 shrink-0 text-faint group-hover/title:text-brand" />
              </a>
              <p className="mt-1 text-sm text-muted">
                <span className="font-medium text-foreground">{job.company}</span>
                {job.location && <span> · {job.location}</span>}
              </p>
            </div>
            <span className={cn("rounded-full border px-2.5 py-1 text-xs font-semibold", meta.tone)}>{meta.label}</span>
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <Pill>{job.remote_type || "remote unknown"}</Pill>
            <Pill>{job.contract_type || "contract unknown"}</Pill>
            <Pill>{formatSalary(job)}</Pill>
            <Pill>
              <Clock3 className="size-3" />
              {formatDate(job.posted_at)}
            </Pill>
            {job.all_sources?.slice(0, 3).map((source) => <Pill key={source}>{source}</Pill>)}
          </div>

          {ranking?.explanations?.length ? (
            <div className="mt-4 grid gap-2 md:grid-cols-[1fr_220px]">
              <ul className="space-y-1.5 text-sm leading-5 text-muted">
                {ranking.explanations.slice(0, 3).map((line) => (
                  <li key={line} className="flex gap-2">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full bg-brand" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
              <div className="grid grid-cols-2 gap-1.5">
                {parts.slice(0, 6).map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-surface-hover/70 px-2 py-1.5">
                    <div className="text-[10px] uppercase tracking-wide text-faint">{label}</div>
                    <div className="text-sm font-semibold text-foreground">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex flex-col gap-2 border-t border-border bg-background/45 p-4 lg:border-l lg:border-t-0">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs uppercase tracking-[0.18em] text-faint">Score</span>
            <span className={cn(`${instrumentSerif.className} text-4xl`, scoreTone(ranking?.score ?? 0))}>{ranking?.score ?? "—"}</span>
          </div>
          <ActionButton busy={busy} icon={CheckCircle2} label="Évaluer" onClick={() => onDecision("evaluate")} active={item.decision === "evaluate"} />
          <ActionButton busy={busy} icon={SkipForward} label="Plus tard" onClick={() => onDecision("save_for_later")} active={item.decision === "save_for_later"} />
          <ActionButton busy={busy} icon={XCircle} label="Ignorer" onClick={() => onDecision("skip")} active={item.decision === "skip"} />
          <button
            type="button"
            onClick={onExport}
            disabled={busy || !!item.exported_to_pipeline_at}
            className={cn(
              "mt-2 inline-flex items-center justify-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition",
              item.exported_to_pipeline_at
                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                : "bg-brand text-brand-foreground hover:bg-brand-200",
              "disabled:opacity-70",
            )}
          >
            {busy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
            {item.exported_to_pipeline_at ? "Dans le pipeline" : "Exporter pipeline"}
          </button>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover"
          >
            <ExternalLink className="size-4" />
            Ouvrir l'offre
          </a>
        </div>
      </div>
    </article>
  );
}

function Pill({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-muted">{children}</span>;
}

function ActionButton({ icon: Icon, label, onClick, active, busy }: { icon: typeof CheckCircle2; label: string; onClick: () => void; active: boolean; busy: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition disabled:opacity-60",
        active ? "border-brand/30 bg-brand-soft text-brand-text" : "border-border bg-surface text-foreground hover:bg-surface-hover",
      )}
    >
      {busy ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
      {label}
    </button>
  );
}
