"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  BriefcaseBusiness,
  CheckCircle2,
  Loader2,
  MapPin,
  RotateCcw,
  Save,
  Search,
  SlidersHorizontal,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type RemotePolicy = "remote" | "hybrid" | "onsite" | "any";

type SearchProfile = {
  id?: number;
  name: string;
  enabled: boolean;
  target_titles: string[];
  positive_keywords: string[];
  negative_keywords: string[];
  required_keywords: string[];
  blocked_titles: string[];
  locations: string[];
  remote_policy: RemotePolicy;
  contract_types: string[];
  seniority_min: number | null;
  seniority_max: number | null;
  salary_min: number | null;
  salary_target: number | null;
  industries_allow: string[];
  industries_block: string[];
  companies_allow: string[];
  companies_block: string[];
  ats_allow: string[];
  sources_enabled: string[];
  freshness_days: number;
  max_results_per_run: number;
  daily_digest_size: number;
  language: string;
  market_mode: string;
};

const LIST_FIELDS = [
  {
    key: "target_titles",
    title: "Titres ciblés",
    description: "Les intitulés qui déclenchent le score titre. Mets les rôles que tu accepterais réellement.",
    placeholder: "AI Engineer\nBackend Engineer\nForward Deployed Engineer",
    icon: BriefcaseBusiness,
  },
  {
    key: "positive_keywords",
    title: "Mots-clés positifs",
    description: "Compétences, domaines ou signaux qui augmentent le score.",
    placeholder: "python\ndjango\nllm\nagent\nplatform",
    icon: Sparkles,
  },
  {
    key: "negative_keywords",
    title: "Mots-clés négatifs",
    description: "Signaux à pénaliser sans forcément rejeter toute l’offre.",
    placeholder: "php\nwordpress\nstage\nalternance",
    icon: SlidersHorizontal,
  },
  {
    key: "required_keywords",
    title: "Mots-clés requis",
    description: "Si renseigné, une offre sans ces termes est rejetée. À utiliser avec parcimonie.",
    placeholder: "django\nai",
    icon: CheckCircle2,
  },
  {
    key: "blocked_titles",
    title: "Titres bloqués",
    description: "Intitulés qui rejettent directement une offre.",
    placeholder: "Sales\nRecruiter\nIntern",
    icon: Search,
  },
  {
    key: "locations",
    title: "Localisations",
    description: "Zones acceptées. Remote est traité comme une localisation utile pour le scoring.",
    placeholder: "Paris\nFrance\nRemote\nEurope",
    icon: MapPin,
  },
] as const;

const CONTRACTS = [
  { value: "cdi", label: "CDI" },
  { value: "freelance", label: "Freelance" },
  { value: "cdd", label: "CDD" },
  { value: "portage", label: "Portage" },
  { value: "alternance", label: "Alternance" },
  { value: "stage", label: "Stage" },
];

const REMOTE_POLICIES: { value: RemotePolicy; label: string; help: string }[] = [
  { value: "hybrid", label: "Hybrid OK", help: "Remote et hybride acceptés, onsite pénalisé/rejeté selon règles." },
  { value: "remote", label: "Remote only", help: "Filtre strict pour les offres remote." },
  { value: "any", label: "Tout accepter", help: "Aucune contrainte remote forte." },
  { value: "onsite", label: "On-site OK", help: "Présentiel accepté." },
];

function emptyProfile(): SearchProfile {
  return {
    name: "default",
    enabled: true,
    target_titles: [],
    positive_keywords: [],
    negative_keywords: [],
    required_keywords: [],
    blocked_titles: [],
    locations: [],
    remote_policy: "hybrid",
    contract_types: [],
    seniority_min: null,
    seniority_max: null,
    salary_min: null,
    salary_target: null,
    industries_allow: [],
    industries_block: [],
    companies_allow: [],
    companies_block: [],
    ats_allow: [],
    sources_enabled: [],
    freshness_days: 7,
    max_results_per_run: 100,
    daily_digest_size: 20,
    language: "fr",
    market_mode: "modes/fr",
  };
}

function splitList(value: string): string[] {
  return value
    .split(/[\n,;]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, arr) => arr.findIndex((candidate) => candidate.toLowerCase() === item.toLowerCase()) === index);
}

function listToText(value: string[] | undefined): string {
  return (value || []).join("\n");
}

function numberOrNull(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  const message = typeof data === "object" && data !== null && "error" in data ? String((data as { error?: unknown }).error || "") : "";
  if (!res.ok || message) throw new Error(message || `Request failed (${res.status})`);
  return data as T;
}

export function DiscoveryProfileView() {
  const [profile, setProfile] = useState<SearchProfile>(emptyProfile);
  const [draftLists, setDraftLists] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    setError("");
    fetchJson<SearchProfile>("/api/discovery/profile?profile=default")
      .then((data) => {
        setProfile({ ...emptyProfile(), ...data });
        setDraftLists(Object.fromEntries(LIST_FIELDS.map((field) => [field.key, listToText(data[field.key])])));
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Impossible de charger le profil"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const completion = useMemo(() => {
    const checks = [
      profile.target_titles.length > 0,
      profile.positive_keywords.length > 0,
      profile.locations.length > 0,
      profile.contract_types.length > 0,
      profile.daily_digest_size > 0,
    ];
    return Math.round((checks.filter(Boolean).length / checks.length) * 100);
  }, [profile]);

  const updateList = (key: keyof SearchProfile, text: string) => {
    setDraftLists((current) => ({ ...current, [key]: text }));
    setProfile((current) => ({ ...current, [key]: splitList(text) }));
    setSaved(false);
  };

  const updateProfile = <K extends keyof SearchProfile>(key: K, value: SearchProfile[K]) => {
    setProfile((current) => ({ ...current, [key]: value }));
    setSaved(false);
  };

  const toggleContract = (value: string) => {
    const current = new Set(profile.contract_types);
    if (current.has(value)) current.delete(value);
    else current.add(value);
    updateProfile("contract_types", Array.from(current));
  };

  const save = () => {
    setSaving(true);
    setSaved(false);
    setError("");
    fetchJson<SearchProfile>("/api/discovery/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    })
      .then((data) => {
        setProfile({ ...emptyProfile(), ...data });
        setDraftLists(Object.fromEntries(LIST_FIELDS.map((field) => [field.key, listToText(data[field.key])])));
        setSaved(true);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Sauvegarde impossible"))
      .finally(() => setSaving(false));
  };

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -left-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/discovery" className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm transition hover:text-foreground">
              <ArrowLeft className="size-3.5" />
              Retour au digest
            </Link>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Profil de recherche
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Ces critères pilotent la collecte, le scoring et la short-list matinale du profil global <span className="font-semibold text-foreground">default</span>.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={load}
              disabled={loading || saving}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-60"
            >
              <RotateCcw className={cn("size-4", loading && "animate-spin")} />
              Recharger
            </button>
            <button
              type="button"
              onClick={save}
              disabled={loading || saving}
              className="inline-flex items-center gap-2 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground shadow-sm transition hover:bg-brand-200 disabled:opacity-60"
            >
              {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
              Sauvegarder
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto grid max-w-7xl gap-5 px-5 py-6 md:px-10 lg:grid-cols-[320px_1fr]">
        <aside className="space-y-4">
          <div className="rounded-3xl border border-border bg-surface p-5 shadow-sm">
            <div className="text-xs uppercase tracking-[0.18em] text-faint">Complétude</div>
            <div className={`${instrumentSerif.className} mt-3 text-5xl text-foreground`}>{completion}%</div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-hover">
              <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${completion}%` }} />
            </div>
            <p className="mt-4 text-sm leading-6 text-muted">
              Ajuste ce profil avec des critères suffisamment larges pour éviter de rater de bonnes offres, puis resserre avec les décisions matinales.
            </p>
          </div>

          <Panel title="Règles principales">
            <SelectField
              label="Politique remote"
              value={profile.remote_policy}
              onChange={(value) => updateProfile("remote_policy", value as RemotePolicy)}
              options={REMOTE_POLICIES.map((policy) => ({ value: policy.value, label: policy.label }))}
            />
            <div className="mt-4">
              <div className="mb-2 text-sm font-semibold text-foreground">Contrats acceptés</div>
              <div className="flex flex-wrap gap-2">
                {CONTRACTS.map((contract) => (
                  <button
                    key={contract.value}
                    type="button"
                    onClick={() => toggleContract(contract.value)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-xs font-semibold transition",
                      profile.contract_types.includes(contract.value)
                        ? "border-brand/30 bg-brand-soft text-brand-text"
                        : "border-border bg-surface text-muted hover:bg-surface-hover",
                    )}
                  >
                    {contract.label}
                  </button>
                ))}
              </div>
            </div>
          </Panel>

          <Panel title="Volumes">
            <NumberField label="Fraîcheur max. jours" value={profile.freshness_days} onChange={(value) => updateProfile("freshness_days", Math.max(1, value || 1))} />
            <NumberField label="Résultats max/run" value={profile.max_results_per_run} onChange={(value) => updateProfile("max_results_per_run", Math.max(1, value || 1))} />
            <NumberField label="Taille digest" value={profile.daily_digest_size} onChange={(value) => updateProfile("daily_digest_size", Math.max(1, value || 1))} />
            <NumberField label="Salaire minimum" value={profile.salary_min} onChange={(value) => updateProfile("salary_min", value)} nullable />
          </Panel>
        </aside>

        <section className="space-y-4">
          {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300">{error}</div>}
          {saved && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">Profil sauvegardé. Relance un run ou recalcule le digest pour appliquer les nouveaux critères.</div>}

          {loading ? (
            <div className="grid min-h-96 place-items-center rounded-3xl border border-border bg-surface/50">
              <div className="flex items-center gap-3 text-muted">
                <Loader2 className="size-5 animate-spin text-brand" />
                Chargement du profil...
              </div>
            </div>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {LIST_FIELDS.map((field) => (
                <ListEditor
                  key={field.key}
                  title={field.title}
                  description={field.description}
                  placeholder={field.placeholder}
                  icon={field.icon}
                  value={draftLists[field.key] ?? ""}
                  count={(profile[field.key] as string[]).length}
                  onChange={(value) => updateList(field.key, value)}
                />
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-border bg-surface p-5 shadow-sm">
      <h2 className={`${instrumentSerif.className} text-2xl text-foreground`}>{title}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </div>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (value: string) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function NumberField({ label, value, nullable, onChange }: { label: string; value: number | null; nullable?: boolean; onChange: (value: number | null) => void }) {
  return (
    <label className="block">
      <span className="text-sm font-semibold text-foreground">{label}</span>
      <input
        type="number"
        min={nullable ? undefined : 1}
        value={value ?? ""}
        onChange={(event) => onChange(numberOrNull(event.target.value))}
        className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand"
      />
    </label>
  );
}

function ListEditor({
  title,
  description,
  placeholder,
  icon: Icon,
  value,
  count,
  onChange,
}: {
  title: string;
  description: string;
  placeholder: string;
  icon: typeof BriefcaseBusiness;
  value: string;
  count: number;
  onChange: (value: string) => void;
}) {
  return (
    <article className="overflow-hidden rounded-3xl border border-border bg-surface shadow-sm">
      <div className="flex items-start justify-between gap-4 border-b border-border bg-surface-hover/45 p-5">
        <div className="flex gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-2xl bg-brand-soft text-brand-text">
            <Icon className="size-5" />
          </div>
          <div>
            <h2 className={`${instrumentSerif.className} text-3xl leading-none text-foreground`}>{title}</h2>
            <p className="mt-2 text-sm leading-5 text-muted">{description}</p>
          </div>
        </div>
        <span className="rounded-full border border-border bg-background px-2.5 py-1 text-xs font-semibold text-muted">{count}</span>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={8}
        className="block w-full resize-y bg-transparent p-5 text-sm leading-6 text-foreground outline-none placeholder:text-faint"
      />
    </article>
  );
}
