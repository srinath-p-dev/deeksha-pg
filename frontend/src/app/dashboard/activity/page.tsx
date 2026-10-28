"use client";

import Link from "next/link";

import { Card, Empty, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/api";
import { fdatetime } from "@/lib/format";
import type { Audit } from "@/lib/types";

export default function ActivityPage() {
  const { data, error } = useApi<Audit[]>("/api/audit?limit=200");
  return (
    <div className="space-y-4">
      <PageHeader title="Activity" subtitle="Every change made in the dashboard (kept even if a tenant is deleted)." />
      <ErrorBox message={error} />
      {!data && !error ? (
        <Loading />
      ) : (
        <Card>
          {!data?.length ? (
            <Empty>No activity yet</Empty>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.map((a) => {
                const body = <div className="whitespace-pre-line text-sm text-slate-800">{a.summary.replace(/\*/g, "")}</div>;
                return (
                  <li key={a.id} className="py-3">
                    {a.entity_type === "tenant" && a.action !== "delete" && a.entity_id ? (
                      <Link href={`/dashboard/tenants/${a.entity_id}`} className="block hover:bg-slate-50">
                        {body}
                      </Link>
                    ) : (
                      body
                    )}
                    <div className="mt-1 text-xs text-slate-500">
                      {a.actor_name} · {fdatetime(a.created_at)}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
