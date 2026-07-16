"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ExternalLink,
  LayoutGrid,
  List,
  Loader2,
  Radar,
  RefreshCw,
  Search,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { CompanyLogo } from "@/components/company-logo";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type TrackedCompany = {
  name: string;
  careers_url: string;
  api?: string;
  scan_method?: string;
  scan_query?: string;
  notes?: string;
  enabled?: boolean;
};

type HealthCompany = { name: string; status: string; detail: string };
type HealthResult = { available: boolean; configured: boolean; companies: HealthCompany[] };

const HEALTH_CACHE_KEY = "portals_health_cache";
const HEALTH_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

function loadCachedHealth(): HealthResult | null {
  try {
    const raw = localStorage.getItem(HEALTH_CACHE_KEY);
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw) as { data: HealthResult; ts: number };
    if (Date.now() - ts > HEALTH_CACHE_TTL_MS) return null;
    return data;
  } catch { return null; }
}

function saveCachedHealth(data: HealthResult) {
  try { localStorage.setItem(HEALTH_CACHE_KEY, JSON.stringify({ data, ts: Date.now() })); } catch { /* */ }
}

const STATUS_TONE: Record<string, { dot: string; label: string; chip: string }> = {
  live: { dot: "bg-emerald-500", label: "Live", chip: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" },
  empty: { dot: "bg-amber-500", label: "Empty", chip: "bg-amber-500/15 text-amber-700 dark:text-amber-400" },
  broken: { dot: "bg-red-500", label: "Broken", chip: "bg-red-500/15 text-red-700 dark:text-red-400" },
  skipped: { dot: "bg-zinc-400", label: "No ATS", chip: "bg-zinc-500/15 text-zinc-600 dark:text-zinc-400" },
};
const STATUS_ORDER = ["broken", "empty", "live", "skipped"];
const ATS_LABELS: Record<string, string> = {
  greenhouse: "Greenhouse",
  ashby: "Ashby",
  lever: "Lever",
  workday: "Workday",
  smartrecruiters: "SmartRecruiters",
  teamtailor: "Teamtailor",
  workable: "Workable",
  other: "Other",
};

function deriveAts(detail: string): string | undefined {
  const m = detail.match(/^(greenhouse|ashby|lever|workday|smartrecruiters|teamtailor|workable)\//i);
  return m ? m[1].toLowerCase() : undefined;
}

export function PortalsListView() {
  const [health, setHealth] = useState<HealthResult | null>(() => loadCachedHealth());
  const [tracked, setTracked] = useState<TrackedCompany[]>([]);
  const [loading, setLoading] = useState(true);
  const [healthLoading, setHealthLoading] = useState(false);
  const [error, setError] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [enabledFilter, setEnabledFilter] = useState<"all" | "enabled" | "disabled">("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  // Load tracked companies on mount
  useEffect(() => {
    setLoading(true);
    fetch("/api/portals", { cache: "no-store" })
      .then((r) => r.json())
      .then((portalsData) => {
        const doc = portalsData?.content ?? {};
        const companies: TrackedCompany[] = Array.isArray(doc.tracked_companies) ? doc.tracked_companies : [];
        setTracked(companies);
      })
      .catch(() => setError("Chargement impossible"))
      .finally(() => setLoading(false));
  }, []);

  const recheck = (skipCache = false) => {
    if (!skipCache && health && (health.companies?.length ?? 0) > 0) {
      // Already have data, show it
      return;
    }
    setHealthLoading(true);
    setError("");
    fetch("/api/portals/verify", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => {
        setHealth(data);
        saveCachedHealth(data);
      })
      .catch(() => setError("Vérification échouée"))
      .finally(() => setHealthLoading(false));
  };

  const healthByName = useMemo(() => {
    const m = new Map<string, HealthCompany>();
    for (const c of health?.companies ?? []) m.set(c.name.toLowerCase(), c);
    return m;
  }, [health]);

  const enriched = useMemo(() => {
    return tracked.map((t) => {
      const h = healthByName.get(t.name.toLowerCase());
      return { ...t, healthStatus: h?.status ?? "unknown", healthDetail: h?.detail ?? "" };
    });
  }, [tracked, healthByName]);

  const filtered = useMemo(() => {
    let result = enriched;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          (c.careers_url ?? "").toLowerCase().includes(q) ||
          (c.notes ?? "").toLowerCase().includes(q)
      );
    }
    if (statusFilter) result = result.filter((c) => c.healthStatus === statusFilter);
    if (enabledFilter === "enabled") result = result.filter((c) => c.enabled !== false);
    if (enabledFilter === "disabled") result = result.filter((c) => c.enabled === false);
    return result.sort((a, b) => (STATUS_ORDER.indexOf(a.healthStatus) ?? 9) - (STATUS_ORDER.indexOf(b.healthStatus) ?? 9));
  }, [enriched, searchQuery, statusFilter, enabledFilter]);

  const counts = useMemo(() => {
    const c = { live: 0, broken: 0, empty: 0, skipped: 0, total: enriched.length };
    for (const e of enriched) {
      if (e.healthStatus === "live") c.live++;
      else if (e.healthStatus === "broken") c.broken++;
      else if (e.healthStatus === "empty") c.empty++;
      else if (e.healthStatus === "skipped") c.skipped++;
    }
    return c;
  }, [enriched]);

  const hasHealthData = !!health && (health.companies?.length ?? 0) > 0;

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-32 -top-40 -z-10 h-96 w-96 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <Radar className="size-3.5 text-brand" />
              {counts.total} entreprises · health: {hasHealthData ? "vérifié" : "à vérifier"}
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Scanner
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Toutes les entreprises suivies par le scanner. Filtrez par statut, recherchez par nom, et vérifiez la santé des portails.
            </p>
            <div className="mt-3 flex items-center gap-3 text-xs text-faint">
              <Link href="/portals" className="transition-colors hover:text-brand">
                ← Dashboard
              </Link>
              <span>·</span>
              <span>Données : <code>portals.yml</code></span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => recheck(!hasHealthData)}
              disabled={healthLoading}
              className="inline-flex items-center gap-2 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground shadow-sm transition-colors hover:bg-brand-200 disabled:opacity-50"
            >
              {healthLoading ? <Loader2 className="size-4 animate-spin" /> : <Radar className="size-4" />}
              {hasHealthData ? "Re-check" : "Health check"}
            </button>
            <button
              onClick={() => { setLoading(true); fetch("/api/portals", { cache: "no-store" }).then(r => r.json()).then(d => { setTracked(Array.isArray(d?.content?.tracked_companies) ? d.content.tracked_companies : []); }).finally(() => setLoading(false)); }}
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition-colors hover:bg-surface-hover disabled:opacity-50"
            >
              <RefreshCw className={cn("size-3.5", loading && "animate-spin")} />
              Recharger
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-5 py-6 md:px-10 space-y-5">
      {error && (
        <p className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-400">
          {error}
        </p>
      )}

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {hasHealthData ? (
          <>
            <StatCard label="Live" value={counts.live} color="text-emerald-600 dark:text-emerald-400" />
            <StatCard label="Empty" value={counts.empty} color="text-amber-600 dark:text-amber-400" />
            <StatCard label="Broken" value={counts.broken} color="text-red-600 dark:text-red-400" />
            <StatCard label="No ATS" value={counts.skipped} color="text-zinc-500 dark:text-zinc-400" />
          </>
        ) : (
          <>
            <StatCard label="Live" value={null} muted />
            <StatCard label="Empty" value={null} muted />
            <StatCard label="Broken" value={null} muted />
            <StatCard label="No ATS" value={null} muted />
          </>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[180px] max-w-xs">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher..."
            className="w-full rounded-xl border border-border bg-surface py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-faint focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/20"
          />
        </div>
        <div className="flex gap-1.5">
          {(["live", "broken", "empty", "skipped"] as const).map((s) => {
            const t = STATUS_TONE[s];
            const active = statusFilter === s;
            return (
              <button
                key={s}
                onClick={() => setStatusFilter(active ? "" : s)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  active ? "border-brand/50 bg-brand/10 text-brand" : "border-border text-muted hover:border-brand/30"
                )}
              >
                <span className={cn("size-1.5 rounded-full", t.dot)} />
                {t.label}
              </button>
            );
          })}
          {(["all", "enabled", "disabled"] as const).map((e) => (
            <button
              key={e}
              onClick={() => setEnabledFilter(e)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                enabledFilter === e ? "border-brand/50 bg-brand/10 text-brand" : "border-border text-muted hover:border-brand/30"
              )}
            >
              {e === "all" ? "Tous" : e === "enabled" ? "Activé" : "Désactivé"}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-surface/60 p-0.5">
          <button
            onClick={() => setViewMode("grid")}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
              viewMode === "grid" ? "bg-brand/10 text-brand" : "text-muted hover:text-foreground"
            )}
          >
            <LayoutGrid className="size-3.5" />
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
              viewMode === "list" ? "bg-brand/10 text-brand" : "text-muted hover:text-foreground"
            )}
          >
            <List className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Company cards */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-brand" />
        </div>
      ) : filtered.length === 0 ? (
        <p className="py-12 text-center text-sm text-muted">
          {searchQuery || statusFilter || enabledFilter !== "all" ? "Aucune entreprise ne correspond aux filtres" : "Aucune entreprise configurée"}
        </p>
      ) : viewMode === "grid" ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((c) => {
            const tone = STATUS_TONE[c.healthStatus] ?? STATUS_TONE.skipped;
            const ats = deriveAts(c.healthDetail) ?? c.api?.split("/").pop()?.split(".")[0] ?? undefined;
            const enabled = c.enabled !== false;
            return (
              <div
                key={c.name}
                className={cn(
                  "group relative flex flex-col gap-2 rounded-2xl border bg-surface/60 p-4 transition-colors hover:border-brand/30",
                  !enabled && "opacity-50",
                  c.healthStatus === "broken" ? "border-red-500/30" : "border-border"
                )}
              >
                <div className="flex items-start gap-3">
                  <CompanyLogo name={c.name} size={28} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold">{c.name}</span>
                      <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold", tone.chip)}>
                        {tone.label}
                      </span>
                    </div>
                    {c.careers_url && (
                      <a
                        href={c.careers_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-0.5 inline-flex items-center gap-1 text-xs text-faint transition-colors hover:text-brand"
                      >
                        <ExternalLink className="size-3 shrink-0" />
                        <span className="truncate max-w-[220px]">{c.careers_url}</span>
                      </a>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  {ats && (
                    <span className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-faint">
                      {ATS_LABELS[ats] ?? ats}
                    </span>
                  )}
                  {c.scan_method && c.scan_method !== "api" && (
                    <span className="rounded bg-surface-hover px-1.5 py-0.5 text-faint">
                      {c.scan_method}
                    </span>
                  )}
                  {c.healthDetail && (
                    <span className="truncate text-faint max-w-[200px]">{c.healthDetail}</span>
                  )}
                </div>

                {c.notes && (
                  <p className="line-clamp-2 text-xs text-faint">{c.notes}</p>
                )}

                <div className="absolute right-3 top-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <Link
                    href="/portals"
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-muted transition-colors hover:border-brand/40 hover:text-brand"
                  >
                    <Wrench className="size-3" /> Dashboard
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        /* List view */
        <div className="overflow-hidden rounded-2xl border border-border bg-surface/40">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-faint">
                <th className="px-4 py-2.5 font-medium">Entreprise</th>
                <th className="px-4 py-2.5 font-medium">ATS</th>
                <th className="px-4 py-2.5 font-medium">Détail</th>
                <th className="px-4 py-2.5 font-medium">Notes</th>
                <th className="px-4 py-2.5 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filtered.map((c) => {
                const tone = STATUS_TONE[c.healthStatus] ?? STATUS_TONE.skipped;
                const ats = deriveAts(c.healthDetail) ?? c.api?.split("/").pop()?.split(".")[0] ?? undefined;
                const enabled = c.enabled !== false;
                return (
                  <tr
                    key={c.name}
                    className={cn(
                      "transition-colors hover:bg-surface-hover/50",
                      !enabled && "opacity-50",
                      c.healthStatus === "broken" && "bg-red-500/5"
                    )}
                  >
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2.5">
                        <CompanyLogo name={c.name} size={20} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{c.name}</span>
                            <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold", tone.chip)}>
                              {tone.label}
                            </span>
                          </div>
                          {c.careers_url && (
                            <a
                              href={c.careers_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-0.5 inline-flex items-center gap-1 text-xs text-faint transition-colors hover:text-brand"
                            >
                              <ExternalLink className="size-3 shrink-0" />
                              <span className="truncate max-w-[280px]">{c.careers_url}</span>
                            </a>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      {ats && (
                        <span className="rounded bg-surface-hover px-1.5 py-0.5 font-mono text-xs text-faint">
                          {ATS_LABELS[ats] ?? ats}
                        </span>
                      )}
                      {c.scan_method && c.scan_method !== "api" && (
                        <span className="ml-1 rounded bg-surface-hover px-1.5 py-0.5 text-xs text-faint">
                          {c.scan_method}
                        </span>
                      )}
                    </td>
                    <td className="max-w-[240px] px-4 py-2.5 text-xs text-faint">
                      <span className="truncate block">{c.healthDetail}</span>
                    </td>
                    <td className="max-w-[280px] px-4 py-2.5 text-xs text-faint">
                      <span className="truncate block">{c.notes}</span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <Link
                        href="/portals"
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[10px] text-muted transition-colors hover:border-brand/40 hover:text-brand"
                      >
                        <Wrench className="size-3" /> Dashboard
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      </main>
    </div>
  );
}

function StatCard({ label, value, color, muted }: { label: string; value: number | null; color?: string; muted?: boolean }) {
  return (
    <div className={cn("rounded-2xl border bg-surface/60 px-4 py-3", muted ? "border-dashed border-border/60" : "border-border")}>
      <div className={cn("text-2xl font-semibold tabular-nums", muted ? "text-faint" : color)}>{value !== null ? value : "—"}</div>
      <div className="mt-0.5 text-xs text-faint">{label}</div>
    </div>
  );
}
