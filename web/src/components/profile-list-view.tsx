"use client";

import { useEffect, useState } from "react";
import {
  ArrowLeft,
  Check,
  Copy,
  FileText,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { instrumentSerif } from "@/lib/fonts";

type Variant = {
  name: string;
  overrides: Record<string, unknown>;
};

type Profile = {
  candidate?: { full_name?: string; email?: string };
  narrative?: { headline?: string };
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { ...init, cache: "no-store" });
  const data = (await res.json()) as unknown;
  const message = typeof data === "object" && data !== null && "error" in data ? String((data as { error?: unknown }).error || "") : "";
  if (!res.ok || message) throw new Error(message || `Request failed (${res.status})`);
  return data as T;
}

function getOverrideCount(overrides: Record<string, unknown>): number {
  return Object.keys(overrides).length;
}

const OVERRIDE_LABELS: Record<string, string> = {
  candidate: "Identité",
  narrative: "Narrative",
  compensation: "Rémunération",
  location: "Localisation",
  languages: "Langues",
  interests: "Intérêts",
  regulations: "Réglementation",
  language: "Output lang",
  spend_tier: "Spend tier",
};

function getOverrideSummary(overrides: Record<string, unknown>): string {
  const keys = Object.keys(overrides);
  if (keys.length === 0) return "Aucun override";
  return keys.map((k) => OVERRIDE_LABELS[k] || k).join(", ");
}

function getOverrideChips(overrides: Record<string, unknown>): Array<{ key: string; label: string; depth: number }> {
  return Object.keys(overrides).map((k) => {
    const val = overrides[k];
    const depth = typeof val === "object" && val !== null ? Object.keys(val as Record<string, unknown>).length : 0;
    return { key: k, label: OVERRIDE_LABELS[k] || k, depth };
  });
}

export function ProfileListView() {
  const [variants, setVariants] = useState<Variant[]>([]);
  const [baseProfile, setBaseProfile] = useState<Profile>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [activeVariant, setActiveVariant] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    setError("");
    if (typeof window !== "undefined") {
      setActiveVariant(localStorage.getItem("profile_active_variant"));
    }
    Promise.all([
      fetchJson<{ variants: Variant[] }>("/api/profile/variants"),
      fetchJson<{ profile: Profile }>("/api/profile"),
    ])
      .then(([vData, pData]) => {
        setVariants(vData.variants);
        setBaseProfile(pData.profile);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Chargement impossible"))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const create = () => {
    if (!newName.trim()) return;
    setCreating(true);
    fetchJson<{ ok: boolean; name: string }>("/api/profile/variants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: newName, overrides: {} }),
    })
      .then(() => { setShowNew(false); setNewName(""); load(); })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Création échouée"))
      .finally(() => setCreating(false));
  };

  const remove = (name: string) => {
    fetchJson<{ ok: boolean }>(`/api/profile/variants/${name}`, { method: "DELETE" })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Suppression échouée"));
  };

  const duplicate = (source: Variant) => {
    const dupName = `${source.name}-copy`;
    fetchJson<{ ok: boolean; name: string }>("/api/profile/variants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: dupName, overrides: source.overrides }),
    })
      .then(() => load())
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Duplication échouée"));
  };

  const baseName = baseProfile.candidate?.full_name || "Profil principal";
  const baseHeadline = baseProfile.narrative?.headline || "";

  return (
    <div className="min-h-screen bg-background">
      <section className="relative isolate overflow-hidden border-b border-border px-5 py-8 md:px-10 md:py-10">
        <div className="absolute inset-0 -z-10 dot-bg opacity-80" />
        <div className="absolute -right-24 -top-32 -z-10 h-80 w-80 rounded-full bg-brand/10 blur-3xl" />
        <div className="mx-auto flex max-w-7xl flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link href="/profile" className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted shadow-sm transition hover:text-foreground">
              <ArrowLeft className="size-3.5" /> Retour au profil
            </Link>
            <h1 className={`${instrumentSerif.className} max-w-4xl text-5xl leading-none tracking-tight text-landing md:text-7xl`}>
              Mes variantes
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted md:text-base">
              Gère les profils alternatifs. Chaque variante reprend le profil principal et ne surcharge que les champs spécifiques.
            </p>
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={load} disabled={loading}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground shadow-sm transition hover:bg-surface-hover disabled:opacity-60">
              Recharger
            </button>
            <button type="button" onClick={() => setShowNew(true)}
              className="inline-flex items-center gap-2 rounded-full bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground shadow-sm transition hover:bg-brand-200">
              <Plus className="size-4" /> Nouvelle variante
            </button>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-5 py-6 md:px-10">
        {error && <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-300">{error}</div>}

        {showNew && (
          <div className="mb-5 rounded-3xl border border-border bg-surface p-5 shadow-sm">
            <h2 className={`${instrumentSerif.className} text-2xl text-foreground`}>Nouvelle variante</h2>
            <p className="mt-2 text-sm text-muted">Crée une variante vide, puis édite-la depuis /profile pour n&apos;override que les champs désirés.</p>
            <div className="mt-4 flex gap-3">
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="data-engineer, ml-engineer..."
                className="flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition focus:border-brand" autoFocus />
              <button type="button" onClick={create} disabled={!newName.trim() || creating}
                className="inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200 disabled:opacity-60">
                {creating ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />} Créer
              </button>
              <button type="button" onClick={() => { setShowNew(false); setNewName(""); }}
                className="rounded-xl border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover">Annuler</button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="grid min-h-96 place-items-center rounded-3xl border border-border bg-surface/50">
            <div className="flex items-center gap-3 text-muted">
              <Loader2 className="size-5 animate-spin text-brand" /> Chargement...
            </div>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {/* Base profile card */}
            <div className={cn("rounded-3xl border-2 bg-surface p-5 shadow-sm transition", !activeVariant ? "border-brand/50 ring-1 ring-brand/20" : "border-border")}>
              <div className="flex items-start justify-between">
                <div>
                  <span className={cn("rounded-full border px-2.5 py-0.5 text-[10px] font-semibold", !activeVariant ? "border-brand/50 bg-brand-soft text-brand-text" : "border-border bg-surface text-faint")}>Principal</span>
                  <h3 className={`${instrumentSerif.className} mt-3 text-2xl text-foreground`}>{baseName}</h3>
                  {baseHeadline && <p className="mt-1 text-sm text-muted">{baseHeadline}</p>}
                </div>
                {!activeVariant && <Check className="size-5 text-brand" />}
              </div>
              <div className="mt-4 flex gap-2">
                <Link href="/profile"
                  className="inline-flex items-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2 text-sm font-semibold text-brand-text transition hover:bg-brand/15">
                  <Check className="size-4" /> Éditer
                </Link>
              </div>
            </div>

            {/* Variant cards */}
            {variants.map((v) => {
              const isActive = activeVariant === v.name;
              return (
                <div key={v.name} className={cn("rounded-3xl border-2 bg-surface p-5 shadow-sm transition", isActive ? "border-brand/50 ring-1 ring-brand/20" : "border-border hover:border-brand/30 hover:shadow-md")}>
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <span className={cn("rounded-full border px-2.5 py-0.5 text-[10px] font-semibold", isActive ? "border-brand/50 bg-brand-soft text-brand-text" : "border-border bg-surface text-faint")}>Variante</span>
                      <h3 className={`${instrumentSerif.className} mt-3 text-2xl text-foreground`}>{v.name}</h3>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {getOverrideChips(v.overrides).map((chip) => (
                          <span key={chip.key} className="inline-flex items-center gap-1 rounded-full border border-brand/30 bg-brand-soft/50 px-2.5 py-0.5 text-[11px] font-medium text-brand-text">
                            <span className="size-1.5 rounded-full bg-brand" />
                            {chip.label}
                          </span>
                        ))}
                      </div>
                      <p className="mt-2 text-xs text-faint">{getOverrideCount(v.overrides)} champ(s) overridé(s)</p>
                    </div>
                    {isActive && <Check className="size-5 shrink-0 text-brand" />}
                  </div>
                  <div className="mt-4 flex gap-2">
                    <Link href={`/profile?variant=${encodeURIComponent(v.name)}`}
                      className="inline-flex items-center gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-2 text-sm font-semibold text-brand-text transition hover:bg-brand/15">
                      <Check className="size-4" /> Éditer
                    </Link>
                    <button type="button" onClick={() => duplicate(v)}
                      className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-foreground transition hover:bg-surface-hover">
                      <Copy className="size-4" />
                    </button>
                    <button type="button" onClick={() => remove(v.name)}
                      className="inline-flex items-center gap-2 rounded-xl border border-border bg-surface px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50 dark:hover:bg-red-500/10">
                      <Trash2 className="size-4" />
                    </button>
                  </div>
                </div>
              );
            })}

            {variants.length === 0 && (
              <div className="col-span-full rounded-3xl border border-dashed border-border bg-surface/30 p-10 text-center">
                <FileText className="mx-auto size-10 text-faint" />
                <p className="mt-4 text-sm text-muted">Aucune variante. Crée une variante pour cibler un type de poste différent.</p>
                <button type="button" onClick={() => setShowNew(true)}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-foreground transition hover:bg-brand-200">
                  <Plus className="size-4" /> Créer ma première variante
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
