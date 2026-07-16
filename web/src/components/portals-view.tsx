"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Check, ChevronDown, ExternalLink, Loader2, Radar, Search, Wand2, Wrench } from "lucide-react";
import { CompanyLogo } from "@/components/company-logo";
import { useJobs, type Job } from "@/components/jobs/job-store";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Company = { name: string; status: string; detail: string };
type Result = { available: boolean; configured: boolean; companies: Company[] };

const HEALTH_CACHE_KEY = "portals_health_cache";
const HEALTH_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour

function loadCachedHealth(): Result | null {
  try {
    const raw = localStorage.getItem(HEALTH_CACHE_KEY);
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw) as { data: Result; ts: number };
    if (Date.now() - ts > HEALTH_CACHE_TTL_MS) return null;
    return data;
  } catch { return null; }
}

function saveCachedHealth(data: Result) {
  try { localStorage.setItem(HEALTH_CACHE_KEY, JSON.stringify({ data, ts: Date.now() })); } catch { /* */ }
}

const TONE: Record<string, { dot: string; label: string; chip: string }> = {
  live: { dot: "bg-emerald-500", label: "live", chip: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" },
  empty: { dot: "bg-amber-500", label: "live · empty", chip: "bg-amber-500/15 text-amber-700 dark:text-amber-400" },
  broken: { dot: "bg-red-500", label: "broken", chip: "bg-red-500/15 text-red-700 dark:text-red-400" },
  skipped: { dot: "bg-zinc-400", label: "no ATS", chip: "bg-surface-hover text-muted" },
};
const STATUS_FILTERS = ["live", "broken", "empty", "skipped"] as const;
const ORDER: Record<string, number> = { broken: 0, empty: 1, live: 2, skipped: 3 };

export function PortalsView() {
  const [res, setRes] = useState<Result | null>(() => loadCachedHealth());
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { jobs, startJob } = useJobs();

  const fixByCompany = useMemo(() => {
    const m = new Map<string, (typeof jobs)[number]>();
    for (const j of jobs) {
      if (j.kind !== "fix-portal" || !j.input) continue;
      const ex = m.get(j.input);
      if (!ex || j.startedAt > ex.startedAt) m.set(j.input, j);
    }
    return m;
  }, [jobs]);

  function check(skipCache = false) {
    if (!skipCache && res && (res.companies?.length ?? 0) > 0) return; // already have data
    setLoading(true);
    fetch("/api/portals/verify")
      .then((r) => r.json())
      .then((data) => { setRes(data); saveCachedHealth(data); })
      .catch(() => setRes({ available: false, configured: false, companies: [] }))
      .finally(() => setLoading(false));
  }

  const companies = res?.companies ?? [];
  const broken = companies.filter((c) => c.status === "broken");
  const liveN = companies.filter((c) => c.status === "live" || c.status === "empty").length;

  const filtered = useMemo(() => {
    let result = [...companies].sort((a, b) => (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9));
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (c) => c.name.toLowerCase().includes(q) || c.detail.toLowerCase().includes(q)
      );
    }
    if (statusFilter) result = result.filter((c) => c.status === statusFilter);
    return result;
  }, [companies, searchQuery, statusFilter]);

  const counts = useMemo(() => {
    const c = { live: 0, broken: 0, empty: 0, skipped: 0, total: companies.length };
    for (const co of companies) {
      if (co.status === "live") c.live++;
      else if (co.status === "broken") c.broken++;
      else if (co.status === "empty") c.empty++;
      else if (co.status === "skipped") c.skipped++;
    }
    return c;
  }, [companies]);

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-32 -top-40 -z-10 h-96 w-96 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm">
              <Radar className="size-3.5 text-brand" />
              {companies.length} entreprises · {(res?.companies?.length ?? 0) > 0 ? "health vérifié" : "health à vérifier"}
            </div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Portals
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Les entreprises que career-ops suit pour de nouveaux rôles. Vérifie la santé des portails pour détecter les liens cassés — un lien cassé signifie que l&apos;entreprise disparaît silencieusement de chaque scan futur.
            </p>
            <p className="mt-2 text-xs text-faint">
              Source : <code className="text-muted">portals.yml</code> — édite-le directement ou demande à l&apos;assistant.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => check(!res)}
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground shadow-sm transition hover:bg-brand-200 disabled:opacity-60"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Radar className="size-4" />}
              {loading ? "Vérification..." : (res && (res.companies?.length ?? 0) > 0) ? "Re-check" : "Check portal health"}
            </button>
            <Link
              href="/portals/list"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover"
            >
              Liste complète →
            </Link>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-5 py-6 md:px-10">
      {/* Stats row */}
      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {res && (res.companies?.length ?? 0) > 0 ? (
          <>
            <Stat label="Live" value={counts.live} color="text-emerald-600 dark:text-emerald-400" />
            <Stat label="Empty" value={counts.empty} color="text-amber-600 dark:text-amber-400" />
            <Stat label="Broken" value={counts.broken} color="text-red-600 dark:text-red-400" />
            <Stat label="No ATS" value={counts.skipped} color="text-zinc-500 dark:text-zinc-400" />
          </>
        ) : (
          <>
            <Stat label="Live" value={null} muted />
            <Stat label="Empty" value={null} muted />
            <Stat label="Broken" value={null} muted />
            <Stat label="No ATS" value={null} muted />
          </>
        )}
      </div>

      <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
        {/* ---- SIDEBAR ---- */}
        <aside className="space-y-4">
          <Panel title="Ajouter une entreprise">
            <p className="text-xs leading-5 text-muted">
              Colle une URL de page carrière ou une description d&apos;entreprise. L&apos;IA détecte l&apos;ATS et pré-configure le scanner.
            </p>
            <PortalExtractorInline onAdded={() => check()} />
          </Panel>

          <Panel title="Actions">
            <button
              onClick={() => check(!res)}
              disabled={loading}
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Radar className="size-4" />}
              {loading ? "Vérification en cours..." : (res && (res.companies?.length ?? 0) > 0) ? "Re-check" : "Check portal health"}
            </button>
            {loading && <p className="text-[11px] text-faint">Requête ATS de chaque entreprise... (~30–60s)</p>}

            <Link
              href="/portals/list"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-muted transition hover:border-brand/40 hover:text-brand"
            >
              Voir la liste complète →
            </Link>
          </Panel>

          {res && !res.available && (
            <div className="rounded-xl border border-dashed border-border bg-surface/30 p-4 text-xs text-muted">
              <code className="text-foreground">verify-portals.mjs</code> introuvable — checkout career-ops complet requis.
            </div>
          )}
          {res && res.available && !res.configured && (
            <div className="rounded-xl border border-dashed border-border bg-surface/30 p-4 text-xs text-muted">
              Pas de <code className="text-foreground">portals.yml</code> — demande à l&apos;assistant de configurer les entreprises.
            </div>
          )}
        </aside>

        {/* ---- MAIN: company list ---- */}
        <div className="space-y-4">
          {res && res.configured && (res.companies?.length ?? 0) > 0 && broken.length > 0 && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm">
              <span className="font-medium text-red-700 dark:text-red-400">
                {broken.length} {broken.length === 1 ? "entreprise silencieuse" : "entreprises silencieuses"} ignorée{broken.length > 1 ? "s" : ""}
              </span>{" "}
              <span className="text-muted">
                — lien carrière cassé. Corrige <code>careers_url</code> dans <code>portals.yml</code>.
              </span>
            </div>
          )}

          {/* Search + filter chips */}
          {res && res.configured && (res.companies?.length ?? 0) > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative flex-1 min-w-[160px] max-w-xs">
                <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher..."
                  className="w-full rounded-xl border border-border bg-surface py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-faint focus:border-brand/50 focus:outline-none focus:ring-1 focus:ring-brand/20"
                />
              </div>
              {STATUS_FILTERS.map((s) => {
                const t = TONE[s];
                const active = statusFilter === s;
                const count = s === "live" ? counts.live : s === "broken" ? counts.broken : s === "empty" ? counts.empty : counts.skipped;
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
                    <span className="tabular-nums text-faint">({count})</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Company list */}
          {res && res.configured && (res.companies?.length ?? 0) > 0 && (
            <ul className="divide-y divide-border overflow-hidden rounded-2xl border border-border bg-surface/40">
              {filtered.length === 0 ? (
                <li className="px-4 py-8 text-center text-sm text-muted">
                  {searchQuery || statusFilter ? "Aucune entreprise ne correspond" : "Aucune entreprise configurée"}
                </li>
              ) : (
                filtered.map((c) => {
                  const t = TONE[c.status] ?? TONE.skipped;
                  return (
                    <li key={c.name} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-hover/50">
                      <CompanyLogo name={c.name} size={22} />
                      <span className={cn("size-1.5 shrink-0 rounded-full", t.dot)} />
                      <div className="min-w-0 flex-1">
                        <span className="text-sm font-medium">{c.name}</span>
                        <span className="ml-2 truncate font-mono text-xs text-faint">{c.detail}</span>
                      </div>
                      <div className="ml-auto flex shrink-0 items-center gap-2">
                        {c.status === "broken" && (
                          <FixAffordance
                            company={c.name}
                            job={fixByCompany.get(c.name)}
                            onFix={() => startJob({ title: `Fix · ${c.name}`, subtitle: "repair portal slug", kind: "fix-portal", input: c.name, page: "/portals" })}
                          />
                        )}
                        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", t.chip)}>{t.label}</span>
                      </div>
                    </li>
                  );
                })
              )}
            </ul>
          )}

          {(!res || (res.companies?.length ?? 0) === 0) && !loading && (
            <div className="grid min-h-64 place-items-center rounded-3xl border border-dashed border-border bg-surface/30">
              <div className="text-center space-y-3">
                <Radar className="mx-auto size-8 text-faint" />
                <p className="text-sm font-medium text-muted">Lance un health check pour voir les entreprises.</p>
                <p className="text-xs text-faint">Le scan vérifie l&apos;accessibilité de chaque ATS (~30–60s).</p>
              </div>
            </div>
          )}
        </div>
      </div>
      </main>
    </div>
  );
}

/* ── Small helpers ──────────────────────────────────────────── */

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-border bg-surface shadow-sm">
      <h3 className={`${instrumentSerif.className} px-5 pt-4 pb-1 text-xl font-semibold text-foreground`}>{title}</h3>
      <div className="space-y-3 border-t border-border px-5 pb-5 pt-3">{children}</div>
    </div>
  );
}

function Stat({ label, value, color, muted }: { label: string; value: number | null; color?: string; muted?: boolean }) {
  return (
    <div className={cn("rounded-2xl border bg-surface/60 px-4 py-3", muted ? "border-dashed border-border/60" : "border-border")}>
      <div className={cn("text-2xl font-semibold tabular-nums", muted ? "text-faint" : color)}>{value !== null ? value : "—"}</div>
      <div className="mt-0.5 text-xs text-faint">{label}</div>
    </div>
  );
}

function FixAffordance({ company, job, onFix }: { company: string; job?: Job; onFix: () => void }) {
  if (job?.status === "running")
    return (
      <Link href={`/jobs/${job.id}`} className="inline-flex items-center gap-1 text-xs font-medium text-brand">
        <Loader2 className="size-3 animate-spin" /> Fixing…
      </Link>
    );
  if (job?.status === "done")
    return (
      <Link href={`/jobs/${job.id}`} className="text-xs font-medium text-emerald-600 dark:text-emerald-400">
        repaired · re-check
      </Link>
    );
  return (
    <button
      onClick={onFix}
      title={`Réparer le slug de ${company}`}
      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-muted transition-colors hover:border-brand/40 hover:text-brand"
    >
      <Wrench className="size-3" /> Fix
    </button>
  );
}

/* ── Inline extractor (sidebar panel) ─────────────────────── */

type PortalExtracted = {
  name: string;
  careers_url: string;
  api: string;
  scan_method: string;
  scan_query: string;
  notes: string;
  ats_platform: string;
  confidence: string;
};

function PortalExtractorInline({ onAdded }: { onAdded?: () => void }) {
  const [text, setText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<{ extracted: PortalExtracted; appended: boolean } | null>(null);

  const extract = () => {
    if (!text.trim()) return;
    setExtracting(true); setError(""); setResult(null);
    fetch("/api/skills/llm/extract-portal", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, persist: false }),
    })
      .then((r) => r.json())
      .then((data) => { if (data.error) setError(data.error); else setResult(data); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Extraction échouée"))
      .finally(() => setExtracting(false));
  };

  const addCompany = () => {
    if (!result?.extracted) return;
    setExtracting(true); setError("");
    fetch("/api/skills/llm/extract-portal", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, persist: true }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.error) {
          if (data.error.includes("portals.yml not found")) {
            setError("portals.yml pas encore créé. Copie d'abord templates/portals.example.yml → portals.yml");
          } else { setError(data.error); }
        } else { setResult(null); setText(""); onAdded?.(); }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Ajout échoué"))
      .finally(() => setExtracting(false));
  };

  return (
    <div className="space-y-3">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={"https://mistral.ai/careers\n\nou\n\nMistral AI — Paris, LLM open-source, page carrière greenhouse.io"}
        rows={4}
        className="w-full resize-y rounded-xl border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-faint focus:border-brand"
      />
      <button
        onClick={extract}
        disabled={extracting || !text.trim()}
        className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2.5 text-sm font-semibold text-brand-text transition hover:bg-brand/15 disabled:opacity-60"
      >
        {extracting ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
        {extracting ? "Analyse..." : "Analyser"}
      </button>

      {error && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-300">{error}</div>
      )}

      {result && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-emerald-700 dark:text-emerald-400">{result.extracted.name}</span>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold",
              result.extracted.confidence === "high" ? "bg-emerald-500/20 text-emerald-700" :
              result.extracted.confidence === "medium" ? "bg-amber-500/20 text-amber-700" :
              "bg-zinc-500/20 text-zinc-700")}>{result.extracted.confidence}</span>
          </div>
          <div className="mt-2 space-y-1 text-xs text-muted">
            <p><span className="font-medium text-foreground">ATS:</span> {result.extracted.ats_platform}</p>
            <p className="flex items-center gap-1">
              <span className="font-medium text-foreground">Careers:</span>
              <a href={result.extracted.careers_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-mono text-brand transition hover:underline">
                <ExternalLink className="size-3" />
                {result.extracted.careers_url}
              </a>
            </p>
            {result.extracted.api && <p><span className="font-medium text-foreground">API:</span> <span className="font-mono">{result.extracted.api}</span></p>}
            {result.extracted.scan_method === "websearch" && <p><span className="font-medium text-foreground">Scan:</span> websearch</p>}
            {result.extracted.notes && <p><span className="font-medium text-foreground">Notes:</span> {result.extracted.notes}</p>}
          </div>
          <button
            onClick={addCompany}
            disabled={extracting}
            className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-500/20 disabled:opacity-60"
          >
            <Check className="size-4" /> Ajouter au scanner
          </button>
        </div>
      )}
    </div>
  );
}
