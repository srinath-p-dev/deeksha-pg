"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge, Card, Empty, ErrorBox, Input, LinkButton, Loading, PageHeader, Tabs } from "@/components/ui";
import { useApi } from "@/lib/api";
import { inr, sharingLabel } from "@/lib/format";
import type { TenantSummary } from "@/lib/types";

type Filter = "current" | "active" | "on_notice" | "vacated" | "all";

export default function TenantsPage() {
  const [filter, setFilter] = useState<Filter>("current");
  const [q, setQ] = useState("");
  const params = new URLSearchParams();
  if (filter !== "all") params.set("status", filter);
  const { data, error } = useApi<TenantSummary[]>(`/api/tenants?${params}`);

  const needle = q.trim().toLowerCase();
  const rows = (data ?? []).filter(
    (t) => !needle || t.name.toLowerCase().includes(needle) || t.phone.includes(needle) || t.room_number.includes(needle),
  );

  return (
    <div className="space-y-4">
      <PageHeader title="Tenants" subtitle={data ? `${rows.length} shown` : undefined} actions={<LinkButton href="/dashboard/tenants/new">+ Add tenant</LinkButton>} />
      <Input placeholder="Search name, phone or room…" value={q} onChange={(e) => setQ(e.target.value)} />
      <Tabs<Filter>
        value={filter}
        onChange={setFilter}
        options={[
          { value: "current", label: "Staying" },
          { value: "active", label: "Active" },
          { value: "on_notice", label: "On notice" },
          { value: "vacated", label: "Vacated" },
          { value: "all", label: "All" },
        ]}
      />
      <ErrorBox message={error} />
      {!data && !error ? (
        <Loading />
      ) : (
        <Card className="p-0">
          {rows.length === 0 ? (
            <Empty>No tenants found</Empty>
          ) : (
            <ul className="divide-y divide-slate-100">
              {rows.map((t) => (
                <li key={t.id}>
                  <Link href={`/dashboard/tenants/${t.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-slate-50">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-medium">{t.name}</span>
                        {t.status !== "active" && <Badge kind={t.status} />}
                      </div>
                      <div className="text-xs text-slate-500">
                        Room {t.room_number} · {sharingLabel(t.sharing)} · {inr(t.rent)}
                        {t.rent_override !== null && <span className="text-violet-700"> (custom)</span>}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      {t.current_month_status && <Badge kind={t.current_month_status} />}
                      {t.outstanding > 0 && <div className="mt-1 text-xs font-semibold text-red-600">Due {inr(t.outstanding)}</div>}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </div>
  );
}
