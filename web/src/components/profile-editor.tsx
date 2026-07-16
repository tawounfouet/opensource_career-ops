"use client";

import { useEffect, useState } from "react";
import {
  Check,
  ChevronDown,
  FileText,
  Globe,
  GraduationCap,
  Loader2,
  MapPin,
  Plus,
  RefreshCcw,
  Save,
  Sparkles,
  User,
  Wand2,
  X,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Candidate = {
  full_name: string;
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  portfolio_url: string;
  github: string;
  twitter: string;
  wechat: string;
  photo: string;
};

type Narrative = {
  headline: string;
  exit_story: string;
  objective: string;
  superpowers: string[];
  proof_points: Array<{ name: string; url: string; hero_metric: string }>;
};

type Compensation = {
  target_range: string;
  currency: string;
  minimum: string;
  location_flexibility: string;
};

type LocationInfo = {
  country: string;
  city: string;
  timezone: string;
  visa_status: string;
};

type Language = {
  language: string;
  level: string;
  note: string;
};

type Profile = {
  candidate: Candidate;
  narrative: Narrative;
  compensation: Compensation;
  location: LocationInfo;
  language: { output: string };
  languages: Language[];
  interests: string[];
  regulations: string[];
  spend_tier: string;
};

type Variant = {
  name: string;
  overrides: Partial<Profile>;
};

const EMPTY_CANDIDATE: Candidate = { full_name: "", email: "", phone: "", location: "", linkedin: "", portfolio_url: "", github: "", twitter: "", wechat: "", photo: "" };
const EMPTY_NARRATIVE: Narrative = { headline: "", exit_story: "", objective: "", superpowers: [], proof_points: [] };
const EMPTY_COMPENSATION: Compensation = { target_range: "", currency: "EUR", minimum: "", location_flexibility: "" };
const EMPTY_LOCATION: LocationInfo = { country: "", city: "", timezone: "", visa_status: "" };

const SECTION_TO_OVERRIDES: Record<string, string[]> = {
  identity: ["candidate"],
  narrative: ["narrative"],
  languages: ["languages"],
  interests: ["interests"],
  regulations: ["regulations"],
  compensation: ["compensation"],
  location: ["location"],
};

const FIELD_LABELS: Record<string, Record<string, string>> = {
  candidate: { full_name: "Nom", email: "Email", phone: "Téléphone", location: "Localisation", linkedin: "LinkedIn", portfolio_url: "Portfolio", github: "GitHub", twitter: "Twitter", wechat: "WeChat", photo: "Photo" },
  narrative: { headline: "Titre", exit_story: "Histoire", objective: "Objectif", superpowers: "Super-pouvoirs" },
  languages: { "*": "Langues" },
  interests: { "*": "Intérêts" },
  regulations: { "*": "Réglementation" },
  compensation: { target_range: "Fourchette", currency: "Devise", minimum: "Minimum", location_flexibility: "Remote" },
  location: { country: "Pays", city: "Ville", timezone: "Fuseau", visa_status: "Visa" },
};

function computeOverriddenFields(base: Profile, variant: Profile): Map<string, string[]> {
  const result = new Map<string, string[]>();
  for (const [section, keys] of Object.entries(SECTION_TO_OVERRIDES)) {
    const labels = FIELD_LABELS[section] ?? {};
    for (const key of keys) {
      const baseVal = (base as Record<string, unknown>)[key];
      const varVal = (variant as Record<string, unknown>)[key];
      if (deepEqual(baseVal, varVal)) continue;
      // For array fields, show single label
      if (labels["*"]) {
        if (!result.has(section)) result.set(section, []);
        result.get(section)!.push(labels["*"]);
      } else {
        // For object fields, find which sub-fields differ
        const baseObj = (typeof baseVal === "object" && baseVal !== null) ? baseVal as Record<string, unknown> : {};
        const varObj = (typeof varVal === "object" && varVal !== null) ? varVal as Record<string, unknown> : {};
        for (const [field, label] of Object.entries(labels)) {
          if (!deepEqual(baseObj[field], varObj[field])) {
            if (!result.has(section)) result.set(section, []);
            result.get(section)!.push(label);
          }
        }
      }
    }
  }
  return result;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  const message = typeof data === "object" && data !== null && "error" in data ? String((data as { error?: unknown }).error || "") : "";
  if (!res.ok || message) throw new Error(message || `Request failed (${res.status})`);
  return data as T;
}

function splitList(value: string): string[] {
  return value.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean);
}

function listToText(value: string[] | undefined): string {
  return (value || []).join("\n");
}

function deepEqual(a: unknown, b: unknown): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function computeOverriddenSections(base: Profile, variant: Profile): Set<string> {
  const sections = new Set<string>();
  for (const [section, keys] of Object.entries(SECTION_TO_OVERRIDES)) {
    for (const key of keys) {
      const baseVal = (base as Record<string, unknown>)[key];
      const varVal = (variant as Record<string, unknown>)[key];
      if (!deepEqual(baseVal, varVal)) {
        sections.add(section);
        break;
      }
    }
  }
  return sections;
}

export function ProfileEditor() {
  const [profile, setProfile] = useState<Profile>({
    candidate: EMPTY_CANDIDATE, narrative: EMPTY_NARRATIVE, compensation: EMPTY_COMPENSATION,
    location: EMPTY_LOCATION, language: { output: "fr" }, languages: [], interests: [], regulations: [], spend_tier: "standard",
  });
  const [variants, setVariants] = useState<Variant[]>([]);
  const [activeVariant, setActiveVariant] = useState<string | null>(() => {
    if (typeof window !== "undefined") return localStorage.getItem("profile_active_variant");
    return null;
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [draftSuperpowers, setDraftSuperpowers] = useState("");
  const [draftInterests, setDraftInterests] = useState("");
  const [draftRegulations, setDraftRegulations] = useState("");
  const [showNewVariant, setShowNewVariant] = useState(false);
  const [newVariantName, setNewVariantName] = useState("");

  // LLM extraction state
  const [extractText, setExtractText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [extractResult, setExtractResult] = useState<{ extracted: Record<string, unknown>; applied: Record<string, unknown>; count: number } | null>(null);
  const [extractError, setExtractError] = useState("");
  const [activeOverrides, setActiveOverrides] = useState<Record<string, unknown>>({});
  const [overriddenSections, setOverriddenSections] = useState<Set<string>>(new Set());
  const [overriddenFields, setOverriddenFields] = useState<Map<string, string[]>>(new Map());

  // Track which sections are expanded
  const [expanded, setExpanded] = useState<Record<string, boolean>>({
    identity: true, narrative: true, languages: false, interests: false,
    regulations: false, compensation: false, location: false,
  });

  const toggle = (key: string) => setExpanded((e) => ({ ...e, [key]: !e[key] }));

  const load = () => {
    setLoading(true);
    setError("");
    const vp = activeVariant ? `?variant=${activeVariant}` : "";
    fetchJson<{ profile: Profile; variants: string[]; active_variant: string | null }>(`/api/profile${vp}`)
      .then((data) => {
        setProfile({
          candidate: { ...EMPTY_CANDIDATE, ...(data.profile.candidate || {}) },
          narrative: { ...EMPTY_NARRATIVE, ...(data.profile.narrative || {}) },
          compensation: { ...EMPTY_COMPENSATION, ...(data.profile.compensation || {}) },
          location: { ...EMPTY_LOCATION, ...(data.profile.location || {}) },
          language: data.profile.language || { output: "fr" },
          languages: data.profile.languages || [],
          interests: data.profile.interests || [],
          regulations: data.profile.regulations || [],
          spend_tier: data.profile.spend_tier || "standard",
        });
        setDraftSuperpowers(listToText(data.profile.narrative?.superpowers));
        setDraftInterests(listToText(data.profile.interests));
        setDraftRegulations(listToText(data.profile.regulations));
        fetchJson<{ variants: Variant[] }>("/api/profile/variants")
          .then((vData) => {
            setVariants(vData.variants);
            if (activeVariant) {
              const match = vData.variants.find((v) => v.name === activeVariant);
              setActiveOverrides(match?.overrides || {});
              // Fetch base profile to compare
              fetchJson<{ profile: Profile }>("/api/profile")
                .then((baseData) => {
                  // Build a full variant profile by merging base + overrides
                  const variantProfile = { ...baseData.profile, ...match?.overrides } as Profile;
                  setOverriddenSections(computeOverriddenSections(baseData.profile, variantProfile));
                  setOverriddenFields(computeOverriddenFields(baseData.profile, variantProfile));
                })
                .catch(() => { setOverriddenSections(new Set()); setOverriddenFields(new Map()); });
            } else {
              setActiveOverrides({});
              setOverriddenSections(new Set());
              setOverriddenFields(new Map());
            }
          })
          .catch(() => {});
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Impossible de charger le profil"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (activeVariant) localStorage.setItem("profile_active_variant", activeVariant);
      else localStorage.removeItem("profile_active_variant");
    }
  }, [activeVariant]);

  const save = () => {
    setSaving(true); setError(""); setSaved(false);
    const vp = activeVariant ? `?variant=${activeVariant}` : "";
    fetchJson<{ ok: boolean }>(`/api/profile${vp}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profile),
    })
      .then(() => { setSaved(true); setTimeout(() => setSaved(false), 2000); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Sauvegarde impossible"))
      .finally(() => setSaving(false));
  };

  const createVariant = () => {
    if (!newVariantName.trim()) return;
    fetchJson<{ ok: boolean; name: string }>("/api/profile/variants", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newVariantName, overrides: {} }),
    })
      .then((data) => { setShowNewVariant(false); setNewVariantName(""); setActiveVariant(data.name); setActiveOverrides({}); load(); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Création variante échouée"));
  };

  const updateCandidate = (key: keyof Candidate, value: string) => {
    setProfile((p) => ({ ...p, candidate: { ...p.candidate, [key]: value } })); setSaved(false);
  };
  const updateNarrative = (key: keyof Narrative, value: string) => {
    setProfile((p) => ({ ...p, narrative: { ...p.narrative, [key]: value } })); setSaved(false);
  };
  const updateCompensation = (key: keyof Compensation, value: string) => {
    setProfile((p) => ({ ...p, compensation: { ...p.compensation, [key]: value } })); setSaved(false);
  };
  const updateLocation = (key: keyof LocationInfo, value: string) => {
    setProfile((p) => ({ ...p, location: { ...p.location, [key]: value } })); setSaved(false);
  };
  const updateListField = (field: "interests" | "regulations", text: string) => {
    if (field === "interests") { setDraftInterests(text); setProfile((p) => ({ ...p, interests: splitList(text) })); }
    else { setDraftRegulations(text); setProfile((p) => ({ ...p, regulations: splitList(text) })); }
    setSaved(false);
  };
  const updateSuperpowers = (text: string) => {
    setDraftSuperpowers(text); setProfile((p) => ({ ...p, narrative: { ...p.narrative, superpowers: splitList(text) } })); setSaved(false);
  };
  const addLanguage = () => { setProfile((p) => ({ ...p, languages: [...p.languages, { language: "", level: "", note: "" }] })); };
  const updateLanguage = (i: number, key: keyof Language, value: string) => {
    setProfile((p) => ({ ...p, languages: p.languages.map((l, idx) => idx === i ? { ...l, [key]: value } : l) })); setSaved(false);
  };
  const removeLanguage = (i: number) => {
    setProfile((p) => ({ ...p, languages: p.languages.filter((_, idx) => idx !== i) })); setSaved(false);
  };

  const runProfileExtraction = () => {
    if (!extractText.trim()) return;
    setExtracting(true); setExtractError(""); setExtractResult(null);
    const vp = activeVariant ? `?variant=${activeVariant}` : "";
    fetchJson<{ extracted: Record<string, unknown>; applied: Record<string, unknown>; count: number }>(`/api/skills/llm/extract-profile${vp}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: extractText, persist: true, variant: activeVariant }),
    })
      .then((data) => { setExtractResult(data); load(); })
      .catch((e: unknown) => setExtractError(e instanceof Error ? e.message : "Extraction échouée"))
      .finally(() => setExtracting(false));
  };

  const completion = (() => {
    const c = profile.candidate;
    const checks = [!!c.full_name, !!c.email, !!profile.narrative.headline, profile.languages.length > 0, profile.interests.length > 0];
    return Math.round((checks.filter(Boolean).length / checks.length) * 100);
  })();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Mon profil
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Informations personnelles, narrative, langues et centres d&apos;intérêt. Ces données alimentent le CV, le scan et l&apos;évaluation.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/profile/list" className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover">
              <FileText className="size-4" />
              Variantes
            </Link>
            <button type="button" onClick={load} disabled={loading || saving}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-60">
              <RefreshCcw className={cn("size-4", loading && "animate-spin")} />
              Recharger
            </button>
            <button type="button" onClick={save} disabled={loading || saving}
              className="inline-flex items-center gap-2 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground shadow-sm transition hover:bg-brand-200 disabled:opacity-60">
              {saving ? <Loader2 className="size-4 animate-spin" /> : saved ? <Check className="size-4" /> : <Save className="size-4" />}
              {saved ? "Sauvegardé" : "Sauvegarder"}
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-5 py-6 md:px-10">
        {error && <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300">{error}</div>}

        {activeVariant && (
          <div className="mb-5 rounded-xl border border-brand/30 bg-brand-soft p-4 text-sm text-brand-text">
            <Sparkles className="mr-2 inline size-4" />
            Mode variante : <strong>{activeVariant}</strong> — les modifications s&apos;appliquent à cette variante.
          </div>
        )}

        {loading ? (
          <div className="grid min-h-96 place-items-center rounded-3xl border border-border bg-surface/50">
            <div className="flex items-center gap-3 text-muted">
              <Loader2 className="size-5 animate-spin text-brand" />
              Chargement du profil...
            </div>
          </div>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[380px_1fr]">
            {/* ---- SIDEBAR ---- */}
            <aside className="space-y-4">
              {/* Complétude */}
              <div className="rounded-3xl border border-border bg-surface p-5 shadow-sm">
                <div className="text-xs uppercase tracking-[0.18em] text-faint">Complétude</div>
                <div className={`${instrumentSerif.className} mt-3 text-5xl text-foreground`}>{completion}%</div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-hover">
                  <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${completion}%` }} />
                </div>
                <p className="mt-4 text-sm leading-6 text-muted">
                  Remplis ton profil pour améliorer la qualité des evaluations et du CV généré.
                </p>
              </div>

              {/* Variant selector */}
              {variants.length > 0 && (
                <Panel title="Variante active">
                  <div className="space-y-2">
                    <button type="button" onClick={() => { setActiveVariant(null); setTimeout(load, 0); }}
                      className={cn("w-full rounded-xl border px-4 py-2.5 text-left text-sm font-medium transition",
                        !activeVariant ? "border-brand/50 bg-brand-soft text-brand-text" : "border-border bg-background text-muted hover:bg-surface-hover")}>
                      Profil principal
                    </button>
                    {variants.map((v) => (
                      <button key={v.name} type="button"
                        onClick={() => { setActiveVariant(v.name); setTimeout(load, 0); }}
                        className={cn("w-full rounded-xl border px-4 py-2.5 text-left text-sm font-medium transition",
                          activeVariant === v.name ? "border-brand/50 bg-brand-soft text-brand-text" : "border-border bg-background text-muted hover:bg-surface-hover")}>
                        {v.name}
                      </button>
                    ))}
                  </div>
                </Panel>
              )}

              {/* CV Preview */}
              <Panel title="Aperçu CV">
                <Link href="/cv" className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2.5 text-sm font-semibold text-brand-text transition hover:bg-brand/15">
                  <FileText className="size-4" />
                  Voir le CV généré
                </Link>
              </Panel>

              {/* LLM Profile Extraction */}
              <Panel title="Extraction LLM">
                <p className="text-xs leading-5 text-muted">
                  Colle un CV, un transcript, ou une description de parcours. L&apos;IA extrait et pré-remplit ton profil.
                </p>
                <textarea
                  value={extractText}
                  onChange={(e) => setExtractText(e.target.value)}
                  placeholder={"Colle ici un CV, un transcript, ou une description de parcours...\n\nL'IA extraira :\n• Identité (nom, email, téléphone...)\n• Narrative (titre, super-pouvoirs)\n• Langues\n• Centres d'intérêt\n• Réglementations / normes\n• Rémunération\n• Localisation"}
                  rows={8}
                  className="mt-2 w-full resize-y rounded-xl border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-faint focus:border-brand"
                />
                <button
                  type="button"
                  onClick={runProfileExtraction}
                  disabled={extracting || !extractText.trim()}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60"
                >
                  {extracting ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
                  {extracting ? "Extraction en cours..." : "Extraire le profil"}
                </button>
                {extractError && (
                  <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-700 dark:text-red-300">{extractError}</div>
                )}
                {extractResult && (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-700 dark:text-emerald-300">
                    <p className="font-semibold">{extractResult.count} champ{extractResult.count !== 1 ? "s" : ""} rempli{extractResult.count !== 1 ? "s" : ""}</p>
                    {extractResult.applied && Object.keys(extractResult.applied).length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {Object.entries(extractResult.applied).map(([k, v]) => (
                          <li key={k} className="flex items-center gap-1.5">
                            <Check className="size-3 shrink-0" />
                            <span className="font-medium">{k}:</span>
                            <span className="truncate">{Array.isArray(v) ? v.join(", ") : String(v)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </Panel>
            </aside>

            {/* ---- MAIN: formulaire ---- */}
            <section className="space-y-4">
              {/* New variant modal */}
              {showNewVariant && (
                <div className="fixed inset-0 z-50 grid place-items-center bg-black/50">
                  <div className="rounded-3xl border border-border bg-surface p-6 shadow-xl">
                    <h2 className={`${instrumentSerif.className} text-2xl text-foreground`}>Créer une variante</h2>
                    <p className="mt-2 text-sm text-muted">Une variante reprend le profil principal et ne surcharge que les champs que tu modifies.</p>
                    <input value={newVariantName} onChange={(e) => setNewVariantName(e.target.value)}
                      placeholder="data-engineer, ml-engineer..."
                      className="mt-4 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand" autoFocus />
                    <div className="mt-4 flex gap-2">
                      <button type="button" onClick={createVariant} disabled={!newVariantName.trim()}
                        className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60">Créer</button>
                      <button type="button" onClick={() => { setShowNewVariant(false); setNewVariantName(""); }}
                        className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover">Annuler</button>
                    </div>
                  </div>
                </div>
              )}

              {/* Identity */}
              <CollapsiblePanel title="Identité" icon={User} expanded={expanded.identity} onToggle={() => toggle("identity")} overridden={overriddenSections.has("identity")} overriddenFields={overriddenFields.get("identity")}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Nom complet" value={profile.candidate.full_name} onChange={(v) => updateCandidate("full_name", v)} placeholder="Audrey KWEKEU" />
                  <Input label="Email" value={profile.candidate.email} onChange={(v) => updateCandidate("email", v)} placeholder="audrey@example.com" type="email" />
                  <Input label="Téléphone" value={profile.candidate.phone} onChange={(v) => updateCandidate("phone", v)} placeholder="+33 7 44 73 70 96" />
                  <Input label="Localisation" value={profile.candidate.location} onChange={(v) => updateCandidate("location", v)} placeholder="Marseille, France" />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="LinkedIn" value={profile.candidate.linkedin} onChange={(v) => updateCandidate("linkedin", v)} placeholder="linkedin.com/in/..." />
                  <Input label="Portfolio" value={profile.candidate.portfolio_url} onChange={(v) => updateCandidate("portfolio_url", v)} placeholder="https://..." />
                  <Input label="GitHub" value={profile.candidate.github} onChange={(v) => updateCandidate("github", v)} placeholder="github.com/..." />
                  <Input label="Twitter/X" value={profile.candidate.twitter} onChange={(v) => updateCandidate("twitter", v)} placeholder="https://x.com/..." />
                </div>
              </CollapsiblePanel>

              {/* Narrative */}
              <CollapsiblePanel title="Narrative" icon={Sparkles} expanded={expanded.narrative} onToggle={() => toggle("narrative")} overridden={overriddenSections.has("narrative")} overriddenFields={overriddenFields.get("narrative")}>
                <Input label="Titre professionnel" value={profile.narrative.headline} onChange={(v) => updateNarrative("headline", v)} placeholder="Ingénieure Qualité & Affaires Réglementaires" />
                <Textarea label="Histoire de sortie" value={profile.narrative.exit_story} onChange={(v) => updateNarrative("exit_story", v)} placeholder="Ce qui te rend unique..." rows={3} />
                <Textarea label="Objectif CV (optionnel)" value={profile.narrative.objective} onChange={(v) => updateNarrative("objective", v)} placeholder="Recherche active d'un poste..." rows={3} />
                <Textarea label="Super-pouvoirs (un par ligne)" value={draftSuperpowers} onChange={updateSuperpowers} placeholder={"Conformité réglementaire\nGestion de projet qualité\nAudits ISO"} rows={4} />
              </CollapsiblePanel>

              {/* Languages */}
              <CollapsiblePanel title="Langues parlées" icon={Globe} expanded={expanded.languages} onToggle={() => toggle("languages")} overridden={overriddenSections.has("languages")} overriddenFields={overriddenFields.get("languages")}>
                {profile.languages.map((lang, i) => (
                  <div key={i} className="flex items-end gap-3">
                    <div className="flex-1 grid gap-3 sm:grid-cols-3">
                      <Input label="Langue" value={lang.language} onChange={(v) => updateLanguage(i, "language", v)} placeholder="Français" />
                      <Input label="Niveau" value={lang.level} onChange={(v) => updateLanguage(i, "level", v)} placeholder="B2, Langue maternelle..." />
                      <Input label="Note" value={lang.note} onChange={(v) => updateLanguage(i, "note", v)} placeholder="TOEIC 865/990" />
                    </div>
                    <button type="button" onClick={() => removeLanguage(i)} className="mb-2 rounded-lg border border-border p-2 text-faint hover:text-red-500"><X className="size-4" /></button>
                  </div>
                ))}
                <button type="button" onClick={addLanguage}
                  className="inline-flex items-center gap-2 rounded-xl border border-dashed border-border px-4 py-2 text-sm font-medium text-muted transition hover:border-brand/30 hover:text-foreground">
                  <Plus className="size-4" /> Ajouter une langue
                </button>
              </CollapsiblePanel>

              {/* Interests */}
              <CollapsiblePanel title="Centres d'intérêt" icon={GraduationCap} expanded={expanded.interests} onToggle={() => toggle("interests")} overridden={overriddenSections.has("interests")} overriddenFields={overriddenFields.get("interests")}>
                <Textarea label="" value={draftInterests} onChange={(v) => updateListField("interests", v)} placeholder={"Chant choral\nVoyage\nPhotographie\nBénévolat"} rows={5} />
              </CollapsiblePanel>

              {/* Regulations */}
              <CollapsiblePanel title="Réglementation & normes" icon={MapPin} expanded={expanded.regulations} onToggle={() => toggle("regulations")} overridden={overriddenSections.has("regulations")} overriddenFields={overriddenFields.get("regulations")}>
                <Textarea label="" value={draftRegulations} onChange={(v) => updateListField("regulations", v)} placeholder={"ISO 13485\nMDSAP\nMarquage CE"} rows={5} />
              </CollapsiblePanel>

              {/* Compensation */}
              <CollapsiblePanel title="Rémunération" icon={Sparkles} expanded={expanded.compensation} onToggle={() => toggle("compensation")} overridden={overriddenSections.has("compensation")} overriddenFields={overriddenFields.get("compensation")}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Fourchette cible" value={profile.compensation.target_range} onChange={(v) => updateCompensation("target_range", v)} placeholder="45000-55000" />
                  <Input label="Devise" value={profile.compensation.currency} onChange={(v) => updateCompensation("currency", v)} placeholder="EUR" />
                  <Input label="Minimum" value={profile.compensation.minimum} onChange={(v) => updateCompensation("minimum", v)} placeholder="40000" />
                  <Input label="Flexibilité remote" value={profile.compensation.location_flexibility} onChange={(v) => updateCompensation("location_flexibility", v)} placeholder="Hybride, 2j/semaine bureau" />
                </div>
              </CollapsiblePanel>

              {/* Location */}
              <CollapsiblePanel title="Localisation" icon={MapPin} expanded={expanded.location} onToggle={() => toggle("location")} overridden={overriddenSections.has("location")} overriddenFields={overriddenFields.get("location")}>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="Pays" value={profile.location.country} onChange={(v) => updateLocation("country", v)} placeholder="France" />
                  <Input label="Ville" value={profile.location.city} onChange={(v) => updateLocation("city", v)} placeholder="Marseille" />
                  <Input label="Fuseau horaire" value={profile.location.timezone} onChange={(v) => updateLocation("timezone", v)} placeholder="CET" />
                  <Input label="Statut visa" value={profile.location.visa_status} onChange={(v) => updateLocation("visa_status", v)} placeholder="Citoyen UE" />
                </div>
              </CollapsiblePanel>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-3xl border border-border bg-surface p-5 shadow-sm">
      <h2 className={`${instrumentSerif.className} text-2xl text-foreground`}>{title}</h2>
      <div className="mt-4 space-y-3">{children}</div>
    </div>
  );
}

function CollapsiblePanel({ title, icon: Icon, expanded, onToggle, overridden, overriddenFields, children }: {
  title: string; icon: React.ComponentType<{ className?: string }>; expanded: boolean; onToggle: () => void; overridden?: boolean; overriddenFields?: string[]; children: React.ReactNode;
}) {
  return (
    <details open={expanded} className="rounded-3xl border border-border bg-surface shadow-sm open:ring-1 open:ring-brand/20">
      <summary onClick={(e) => { e.preventDefault(); onToggle(); }}
        className="flex cursor-pointer items-center justify-between px-5 py-4 text-2xl font-semibold text-foreground hover:bg-surface-hover">
        <span className={`${instrumentSerif.className} flex items-center gap-2 flex-wrap`}>
          <Icon className="size-5 text-brand" /> {title}
          {overridden && overriddenFields && overriddenFields.length > 0 ? (
            <span className="ml-1 inline-flex items-center gap-1 text-[10px]">
              {overriddenFields.map((f) => (
                <span key={f} className="inline-flex items-center gap-0.5 rounded-full border border-brand/30 bg-brand-soft/50 px-1.5 py-0.5 font-semibold text-brand-text">
                  <span className="size-1 rounded-full bg-brand" />
                  {f}
                </span>
              ))}
            </span>
          ) : overridden ? (
            <span className="ml-1 inline-flex items-center gap-1 rounded-full border border-brand/30 bg-brand-soft/50 px-2 py-0.5 text-[10px] font-semibold text-brand-text">
              <span className="size-1.5 rounded-full bg-brand" />
              variante
            </span>
          ) : null}
        </span>
        <ChevronDown className={cn("size-5 text-muted transition-transform", expanded && "rotate-180")} />
      </summary>
      <div className="space-y-3 border-t border-border px-5 pb-5 pt-4">{children}</div>
    </details>
  );
}

function Input({ label, value, placeholder, type = "text", onChange }: { label: string; value: string; placeholder?: string; type?: string; onChange: (value: string) => void }) {
  return (
    <label className="block">
      {label && <span className="text-sm font-semibold text-foreground">{label}</span>}
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand" />
    </label>
  );
}

function Textarea({ label, value, placeholder, rows = 5, onChange }: { label: string; value: string; placeholder?: string; rows?: number; onChange: (value: string) => void }) {
  return (
    <label className="block">
      {label && <span className="text-sm font-semibold text-foreground">{label}</span>}
      <textarea value={value} placeholder={placeholder} rows={rows} onChange={(e) => onChange(e.target.value)}
        className="mt-2 w-full resize-y rounded-xl border border-border bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-faint focus:border-brand" />
    </label>
  );
}
