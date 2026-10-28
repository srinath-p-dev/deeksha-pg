"use client";

import Link from "next/link";
import { useState } from "react";

import { PaymentModal, type PayTarget } from "@/components/PaymentModal";
import { Badge, Button, Card, Empty, ErrorBox, Loading, PageHeader, Stat, Tabs } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { inr, monthKey, monthLabel, shiftMonth, todayIST } from "@/lib/format";
import type { MonthView, RentStatus } from "@/lib/types";

type Filter = "all" | RentStatus;

export default function RentPage() {
  const [month, setMonth] = useState(monthKey(todayIST()));
  const [filter, setFilter] = useState<Filter>("all");
  const [pay, setPay] = useState<PayTarget | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { data, error, reload } = useApi<MonthView>(`/api/rent?month=${month}`);

  const rows = (data?.rows ?? []).filter((r) => filter === "all" || r.record.status === filter);

  async function generate() {
    const res = await api<{ created: number }>(`/api/rent/generate?month=${month}`, { method: "POST" });
    setNotice(res.created ? `Created ${res.created} rent record(s).` : "All rent records already exist.");
    reload();
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Rent" />
      <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-2">
        <Button variant="ghost" onClick={() => setMonth(shiftMonth(month, -1))}>
          ‹ Prev
        </Button>
        <div className="font-semibold">{monthLabel(`${month}-01`)}</div>
        <Button variant="ghost" onClick={() => setMonth(shiftMonth(month, 1))}>
          Next ›
        </Button>
      </div>

      <ErrorBox message={error} />
      {!data && !error && <Loading />}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Expected" value={inr(data.expected)} />
            <Stat label="Collected" value={inr(data.collected)} tone="green" />
            <Stat label="Pending" value={inr(data.pending)} tone={data.pending ? "red" : undefined} />
          </div>
          <Tabs<Filter>
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: `All (${data.rows.length})` },
              { value: "unpaid", label: `Unpaid (${data.counts.unpaid})` },
              { value: "partial", label: `Partial (${data.counts.partial})` },
              { value: "paid", label: `Paid (${data.counts.paid})` },
            ]}
          />
          <Card className="p-0">
            {rows.length === 0 ? (
              <Empty>No rent records{filter !== "all" ? " with this status" : " for this month"}.</Empty>
            ) : (
              <ul className="divide-y divide-slate-100">
                {rows.map(({ record: r, tenant_name, room_number, tenant_status }) => (
                  <li key={r.id} className="flex items-center justify-between gap-3 px-4 py-3">
                    <Link href={`/dashboard/tenants/${r.tenant_id}`} className="min-w-0">
                      <div className="truncate font-medium">
                        <span className="mr-2 text-slate-500">{room_number}</span>
                        {tenant_name}
                        {tenant_status === "vacated" && <span className="ml-1 text-xs text-slate-500">(vacated)</span>}
                      </div>
                      <div className="text-xs text-slate-600">
                        Due {inr(r.amount_due)} · Paid {inr(r.amount_paid)}
                      </div>
                    </Link>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge kind={r.status} />
                      {r.balance > 0 && (
                        <Button small onClick={() => setPay({ record: r, tenantName: tenant_name })}>
                          Pay {inr(r.balance)}
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <div className="text-sm text-slate-600">
            Rent records are created automatically on the 1st of each month.{" "}
            <button className="text-rose-700 underline" onClick={generate}>
              Create missing records now
            </button>
            {notice && <span className="ml-2 text-green-700">{notice}</span>}
          </div>
        </>
      )}

      <PaymentModal
        target={pay}
        onClose={() => setPay(null)}
        onSaved={() => {
          setPay(null);
          reload();
        }}
      />
    </div>
  );
}
