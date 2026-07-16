export function djangoApiBase(): string | null {
  const raw = process.env.CAREER_OPS_API_URL?.trim();
  if (!raw) return null;
  return raw.replace(/\/+$/, "");
}

export function djangoEnabled(): boolean {
  return djangoApiBase() !== null;
}

export async function fetchDjangoJson(path: string, init?: RequestInit): Promise<unknown | null> {
  const base = djangoApiBase();
  if (!base) return null;
  const apiPath = path.startsWith("/") ? path : `/${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2_500);
  try {
    const res = await fetch(`${base}${apiPath}`, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

export async function djangoJsonResponse(path: string, init?: RequestInit): Promise<Response | null> {
  const base = djangoApiBase();
  if (!base) return null;
  const apiPath = path.startsWith("/") ? path : `/${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2_500);
  try {
    const res = await fetch(`${base}${apiPath}`, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });
    const text = await res.text();
    return new Response(text, {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

export async function djangoResponse(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<Response | null> {
  const base = djangoApiBase();
  if (!base) return null;
  const apiPath = path.startsWith("/") ? path : `/${path}`;
  const controller = new AbortController();
  const timeoutMs = init?.timeoutMs;
  const timeout = timeoutMs ? setTimeout(() => controller.abort(), timeoutMs) : null;
  const { timeoutMs: _timeoutMs, ...fetchInit } = init ?? {};
  void _timeoutMs;
  try {
    const res = await fetch(`${base}${apiPath}`, {
      ...fetchInit,
      headers: {
        ...(fetchInit.body ? { "Content-Type": "application/json" } : {}),
        ...(fetchInit.headers ?? {}),
      },
      cache: "no-store",
      signal: controller.signal,
    });
    return res;
  } catch {
    return null;
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}
