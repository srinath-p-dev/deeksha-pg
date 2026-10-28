"use client";

import { useEffect, useState } from "react";

import { Badge, Button, Card, Empty, ErrorBox, Loading, PageHeader, Tabs } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { fdatetime, phone } from "@/lib/format";
import type { Message, WhatsAppStatus } from "@/lib/types";

const KIND: Record<Message["kind"], string> = {
  rent_reminder: "Rent reminder",
  owner_report: "Unpaid report",
  owner_change: "Change alert",
  system: "System",
};

type Filter = "all" | "pending" | "sent" | "failed";

export default function MessagesPage() {
  return (
    <div className="space-y-4">
      <PageHeader title="WhatsApp" subtitle="Bot connection, manual sends and the log of every message." />
      <Connection />
      <ManualActions />
      <MessageLog />
    </div>
  );
}

function Connection() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    const check = () =>
      api<WhatsAppStatus>("/api/whatsapp/status").then(
        (s) => alive && setStatus(s),
        (e: Error) => alive && setError(e.message),
      );
    check();
    // Poll quickly while waiting for a QR scan, slowly otherwise
    const t = setInterval(check, status?.connected ? 30_000 : 4_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [status?.connected]);

  async function test() {
    setInfo(null);
    setError(null);
    try {
      await api("/api/whatsapp/test", { method: "POST" });
      setInfo("Test message queued — it should arrive on the owner's WhatsApp within a minute.");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function unlink() {
    if (!window.confirm("Unlink this WhatsApp number? You'll need to scan a new QR code to send messages again.")) return;
    await api("/api/whatsapp/logout", { method: "POST" }).catch((e: Error) => setError(e.message));
  }

  if (!status) return <Card title="Connection">{error ? <ErrorBox message={error} /> : <Loading />}</Card>;

  return (
    <Card title="Connection">
      {status.connected ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-green-700">
            <span className="h-3 w-3 rounded-full bg-green-500" /> Connected as <b>{phone(status.me)}</b>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={test}>
              Send test message to owner
            </Button>
            <Button variant="ghost" onClick={unlink}>
              Unlink number
            </Button>
          </div>
        </div>
      ) : !status.reachable ? (
        <ErrorBox message="The WhatsApp service isn't running. On the server: docker compose up -d whatsapp" />
      ) : status.qr ? (
        <div className="space-y-3">
          <p className="text-sm">
            On the bot phone: <b>WhatsApp → Settings → Linked devices → Link a device</b>, then scan:
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={status.qr} alt="WhatsApp QR code" className="mx-auto h-64 w-64 rounded-lg border" />
          <p className="text-center text-xs text-slate-500">The code refreshes automatically.</p>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-amber-700">
          <span className="h-3 w-3 animate-pulse rounded-full bg-amber-500" /> {status.state === "connecting" ? "Connecting…" : `Disconnected (${status.state}) — reconnecting automatically…`}
        </div>
      )}
      {info && <p className="mt-3 text-sm text-green-700">{info}</p>}
      <div className="mt-3">
        <ErrorBox message={error} />
      </div>
    </Card>
  );
}

function ManualActions() {
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(path: string, confirmText: string, done: (r: { queued: number | boolean }) => string) {
    if (!window.confirm(confirmText)) return;
    setError(null);
    try {
      setResult(done(await api(path, { method: "POST" })));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Send now">
      <p className="mb-3 text-sm text-slate-600">
        Automatic schedule: tenant reminders on the 5th–8th at 5 PM, unpaid report to owner on the 9th. Use these buttons to send outside the schedule. Each
        tenant gets at most one reminder per day.
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          onClick={() =>
            run("/api/jobs/reminders", "Send a rent reminder now to every tenant who hasn't paid in full?", (r) => `${r.queued} reminder(s) queued.`)
          }
        >
          Send rent reminders
        </Button>
        <Button
          variant="secondary"
          onClick={() =>
            run("/api/jobs/owner-report", "Send this month's unpaid report to the owner's WhatsApp?", (r) =>
              r.queued ? "Report queued." : "This month's report was already sent.",
            )
          }
        >
          Send unpaid report to owner
        </Button>
      </div>
      {result && <p className="mt-3 text-sm text-green-700">{result}</p>}
      <ErrorBox message={error} />
    </Card>
  );
}

function MessageLog() {
  const [filter, setFilter] = useState<Filter>("all");
  const query = filter === "all" ? "" : `&status=${filter}`;
  const { data, error, reload } = useApi<Message[]>(`/api/messages?limit=100${query}`);
  const [open, setOpen] = useState<number | null>(null);

  async function retry(id: number) {
    await api(`/api/messages/${id}/retry`, { method: "POST" });
    reload();
  }

  return (
    <Card title="Message log" actions={<Button small variant="ghost" onClick={reload}>Refresh</Button>}>
      <Tabs<Filter>
        value={filter}
        onChange={setFilter}
        options={[
          { value: "all", label: "All" },
          { value: "pending", label: "Pending" },
          { value: "sent", label: "Sent" },
          { value: "failed", label: "Failed" },
        ]}
      />
      <ErrorBox message={error} />
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <Empty>No messages</Empty>
      ) : (
        <ul className="mt-2 divide-y divide-slate-100">
          {data.map((m) => (
            <li key={m.id} className="py-2.5">
              <button className="flex w-full items-center justify-between gap-2 text-left" onClick={() => setOpen(open === m.id ? null : m.id)}>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">
                    {KIND[m.kind]} → {phone(m.recipient)}
                  </div>
                  <div className="text-xs text-slate-500">
                    {fdatetime(m.created_at)}
                    {m.sent_at && ` · sent ${fdatetime(m.sent_at)}`}
                    {m.error && ` · ${m.error}`}
                  </div>
                </div>
                <Badge kind={m.status} />
              </button>
              {open === m.id && (
                <div className="mt-2 space-y-2">
                  <pre className="whitespace-pre-wrap rounded-lg bg-slate-50 p-3 font-sans text-sm">{m.body}</pre>
                  {["failed", "unknown", "expired"].includes(m.status) && (
                    <Button small variant="secondary" onClick={() => retry(m.id)}>
                      Send again
                    </Button>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
