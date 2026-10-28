"use client";

import { useState } from "react";

import { Button, ErrorBox, Loading, Tabs } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { inr, monthKey, monthLabel, shiftMonth, todayIST } from "@/lib/format";
import type { MonthView, PaymentMode, RentRecord } from "@/lib/types";

type Row = MonthView["rows"][number];

/** One checkbox per tenant: tick = paid in full for the month. */
export default function ChecklistPage() {
  const [month, setMonth] = useState(monthKey(todayIST()));
  const [mode, setMode] = useState<PaymentMode>("upi");
  const [onlyUnpaid, setOnlyUnpaid] = useState(false);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data, error: loadError, setData } = useApi<MonthView>(`/api/rent?month=${month}`);

  async function toggle(row: Row) {
    const r = row.record;
    const paid = r.status === "paid";
    if (paid && !window.confirm(`Mark ${row.tenant_name} as NOT paid?`)) return;
    setBusy(r.id);
    setError(null);
    try {
      const updated = await api<RentRecord>(`/api/rent-records/${r.id}/${paid ? "unmark-paid" : "mark-paid"}`, {
        body: paid ? {} : { mode },
      });
      setData((d) => d && { ...d, rows: d.rows.map((x) => (x.record.id === r.id ? { ...x, record: updated } : x)) });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const rows = data?.rows ?? [];
  const paidCount = rows.filter((r) => r.record.status === "paid").length;
  const pending = rows.reduce((sum, r) => sum + r.record.balance, 0);
  const rooms = new Map<string, Row[]>();
  for (const row of rows) {
    if (onlyUnpaid && row.record.status === "paid") continue;
    rooms.set(row.room_number, [...(rooms.get(row.room_number) ?? []), row]);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
          ‹
        </Button>
        <div className="text-center">
          <h1 className="text-xl font-bold">{monthLabel(`${month}-01`)}</h1>
          {data && (
            <p className="text-sm text-slate-600">
              {paidCount} of {rows.length} paid
              {pending > 0 && <span className="text-red-600"> · {inr(pending)} pending</span>}
            </p>
          )}
        </div>
        <Button variant="ghost" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Next month">
          ›
        </Button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-slate-600">Paid by</span>
          <Tabs<PaymentMode>
            value={mode}
            onChange={setMode}
            options={[
              { value: "upi", label: "UPI" },
              { value: "cash", label: "Cash" },
              { value: "bank", label: "Bank" },
            ]}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={onlyUnpaid} onChange={(e) => setOnlyUnpaid(e.target.checked)} />
          Only unpaid
        </label>
      </div>

      <ErrorBox message={error ?? loadError} />
      {!data && !loadError && <Loading />}
      {data && rows.length === 0 && <p className="py-8 text-center text-slate-500">No rent for this month yet.</p>}
      {data && rows.length > 0 && rooms.size === 0 && <p className="py-8 text-center text-green-700">Everyone has paid 🎉</p>}

      <div className="grid gap-3 sm:grid-cols-2">
        {[...rooms].map(([room, people]) => (
          <section key={room} className="rounded-xl border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-2 text-sm font-semibold text-slate-500">Room {room}</h2>
            <ul>
              {people.map((row) => {
                const r = row.record;
                const paid = r.status === "paid";
                return (
                  <li key={r.id}>
                    <label className={`flex cursor-pointer items-center gap-3 px-4 py-3 ${busy === r.id ? "opacity-50" : ""}`}>
                      <input
                        type="checkbox"
                        className="h-6 w-6 shrink-0 accent-green-600"
                        checked={paid}
                        disabled={busy === r.id}
                        onChange={() => toggle(row)}
                      />
                      <span className={`flex-1 truncate ${paid ? "text-slate-500" : "font-medium"}`}>{row.tenant_name}</span>
                      <span className={`shrink-0 text-sm ${paid ? "text-green-700" : "text-red-600"}`}>
                        {paid ? "Paid ✓" : r.amount_paid > 0 ? `${inr(r.balance)} left` : inr(r.balance)}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
