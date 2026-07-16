import { assembleDedupContext } from "@/lib/core/discover";
import { djangoJsonResponse } from "@/lib/django-api";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// The client fetches this once before opening the AI stream and uses the set as a
// silent dedup backstop in the envelope parser (drops any AI candidate whose URL
// is already known). Keeps the stream itself pure text/plain.
export async function GET() {
  const django = await djangoJsonResponse("/api/explore/ai/known");
  if (django) return django;

  try {
    const { urls } = assembleDedupContext();
    return Response.json({ urls: [...urls] });
  } catch {
    return Response.json({ urls: [] });
  }
}
