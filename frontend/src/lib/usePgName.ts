"use client";

import { useEffect, useState } from "react";

import type { PublicSite } from "./types";

/** The PG's name as entered under Website (falls back while loading). */
export function usePgName(fallback = "PG Manager"): string {
  const [name, setName] = useState(fallback);
  useEffect(() => {
    let alive = true;
    fetch("/api/public/site")
      .then((r) => (r.ok ? (r.json() as Promise<PublicSite>) : null))
      .then((site) => {
        if (alive && site?.content.pg_name) setName(site.content.pg_name);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return name;
}
