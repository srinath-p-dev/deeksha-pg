"use client";

import Link from "next/link";

import { Badge, Card, Empty, ErrorBox, LinkButton, Loading, PageHeader, Stat } from "@/components/ui";
import { useApi } from "@/lib/api";
import { fdate, fdatetime, inr, monthLabel, phone } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

export default function DashboardHome() {
  const { data: d, error } = useApi<Dashboard>("/api/dashboard");
  if (error) return <ErrorBox message={error} />;
  if (!d) return <Loading />;

  const pct = d.rent.expected ? Math.round((d.rent.collected / d.rent.expected) * 100) : 0;

  return (
    <div className="space-y-4">
      <PageHeader
        title={`${monthLabel(d.month)} overview`}
        subtitle={`Today: ${fdate(d.today)}`}
        actions={
          <>
            <LinkButton href="/dashboard/tenants/new">+ Add tenant</LinkButton>
            <LinkButton href="/dashboard/rent" variant="secondary">
              Record payment
            </LinkButton>
          </>
        }
      />

      {!d.site_ready && (
        <Link href="/dashboard/site" className="block rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          👋 First time? Fill in your PG name, address and phone under <b>Website</b> — they appear on the public site and in WhatsApp messages. →
        </Link>
      )}
      {!d.owner_whatsapp_set && (
        <ErrorBox message="Owner WhatsApp number is not set — you won't get change alerts. Set it in Settings." />
      )}

      <Card>
        <div className="flex items-end justify-between">
          <div>
            <div className="text-sm text-slate-500">Collected this month</div>
            <div className="text-3xl font-bold text-green-700">{inr(d.rent.collected)}</div>
            <div className="text-sm text-slate-500">of {inr(d.rent.expected)} expected</div>
          </div>
          <div className="text-right">
            <div className="text-sm text-slate-500">Pending</div>
            <div className="text-2xl font-bold text-red-600">{inr(d.rent.pending)}</div>
          </div>
        </div>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full bg-green-500" style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-3 flex gap-3 text-sm">
          <span>✅ Paid {d.rent.paid}</span>
          <span>🟡 Partial {d.rent.partial}</span>
          <span>🔴 Unpaid {d.rent.unpaid}</span>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Tenants" value={d.tenants.active + d.tenants.on_notice} sub={`${d.tenants.on_notice} on notice`} />
        <Stat label="Free beds" value={d.rooms.free_beds} sub={`${d.rooms.empty} empty rooms`} tone="green" />
        <Stat label="Deposit due" value={inr(d.deposit_pending)} tone={d.deposit_pending ? "amber" : undefined} />
        <Stat
          label="WhatsApp"
          value={d.whatsapp.connected ? "Connected" : "Offline"}
          tone={d.whatsapp.connected ? "green" : "red"}
          sub={`${d.messages_7d.sent} sent · ${d.messages_7d.failed} failed (7d)`}
        />
      </div>

      <Card title={`Not fully paid (${d.unpaid.length})`}>
        {d.unpaid.length === 0 ? (
          <Empty>Everyone has paid 🎉</Empty>
        ) : (
          <ul className="divide-y divide-slate-100">
            {d.unpaid.map((u) => (
              <li key={u.tenant_id}>
                <Link href={`/dashboard/tenants/${u.tenant_id}`} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{u.name}</div>
                    <div className="text-xs text-slate-500">
                      Room {u.room} · {phone(u.phone)} · {u.label}
                    </div>
                  </div>
                  <div className="text-right font-semibold text-red-600">{inr(u.amount)}</div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Moving out">
          {d.on_notice.length === 0 ? (
            <Empty>No one on notice</Empty>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.on_notice.map((t) => (
                <li key={t.id}>
                  <Link href={`/dashboard/tenants/${t.id}`} className="flex justify-between py-2">
                    <span>
                      {t.name} <span className="text-slate-500">· Room {t.room}</span>
                    </span>
                    <Badge kind="on_notice">{t.move_out_date ? fdate(t.move_out_date) : "date not set"}</Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent activity" actions={<Link href="/dashboard/activity" className="text-sm text-rose-700">All →</Link>}>
          {d.recent_activity.length === 0 ? (
            <Empty>No activity yet</Empty>
          ) : (
            <ul className="space-y-2">
              {d.recent_activity.map((a) => (
                <li key={a.id} className="text-sm">
                  <div className="line-clamp-2 whitespace-pre-line text-slate-800">{a.summary.split("\n")[0].replace(/\*/g, "")}</div>
                  <div className="text-xs text-slate-500">
                    {a.actor_name} · {fdatetime(a.created_at)}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
