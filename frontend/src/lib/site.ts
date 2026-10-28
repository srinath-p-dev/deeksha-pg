import type { Metadata } from "next";
import { connection } from "next/server";
import { cache } from "react";

import type { PublicSite } from "./types";

const API = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

/** Fetch public site content on the server, at request time (always fresh).
 *  Wrapped in cache() so the page and its metadata share one request. */
export const getPublicSite = cache(async (): Promise<PublicSite | null> => {
  await connection(); // render per request, never at build time
  try {
    const res = await fetch(`${API}/api/public/site`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as PublicSite;
  } catch {
    return null;
  }
});

/** Browser-tab title + Google description built from the content entered in the app. */
export async function siteMetadata(page?: string): Promise<Metadata> {
  const site = await getPublicSite();
  const c = site?.content;
  const name = c?.pg_name || "PG";
  const kind = c?.who_can_stay ? `${c.who_can_stay} PG` : "PG";
  return {
    title: page ? `${page} — ${name}` : c?.tagline ? `${name} — ${c.tagline}` : name,
    description: c?.tagline || `${name}: ${kind} with rooms for single, double and triple sharing.`,
  };
}
