"use client";

import { useState } from "react";

import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader, Textarea } from "@/components/ui";
import { api, useApi } from "@/lib/api";

type AppSettings = { owner_whatsapp: string; payment_note: string };

export default function SettingsPage() {
  const { data, error } = useApi<AppSettings>("/api/settings");
  return (
    <div className="space-y-4">
      <PageHeader title="Settings" />
      {error ? <ErrorBox message={error} /> : !data ? <Loading /> : <AlertSettings initial={data} />}
      <ChangePassword />
      <Card title="Session">
        <Button
          variant="secondary"
          onClick={async () => {
            await api("/api/auth/logout", { method: "POST" });
            window.location.href = "/login";
          }}
        >
          Log out
        </Button>
      </Card>
    </div>
  );
}

function AlertSettings({ initial }: { initial: AppSettings }) {
  const [owner, setOwner] = useState(initial.owner_whatsapp.replace(/^91/, ""));
  const [note, setNote] = useState(initial.payment_note);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save() {
    setError(null);
    try {
      await api("/api/settings", { method: "PUT", body: { owner_whatsapp: owner, payment_note: note } });
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="WhatsApp messages">
      <div className="space-y-3">
        <Field label="Owner WhatsApp number" hint="Gets a message for every change, payment, and the unpaid report on the 9th.">
          <Input type="tel" value={owner} onChange={(e) => (setSaved(false), setOwner(e.target.value))} />
        </Field>
        <Field label="Payment details for reminders" hint='Added to every rent reminder, e.g. "Pay by UPI to yourpg@okaxis or cash at the office."'>
          <Textarea value={note} onChange={(e) => (setSaved(false), setNote(e.target.value))} />
        </Field>
        <ErrorBox message={error} />
        <div className="flex items-center gap-3">
          <Button onClick={save}>Save</Button>
          {saved && <span className="text-sm text-green-700">Saved ✓</span>}
        </div>
      </div>
    </Card>
  );
}

function ChangePassword() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function save() {
    setError(null);
    try {
      await api("/api/auth/change-password", { body: { current_password: current, new_password: next } });
      setDone(true);
      setCurrent("");
      setNext("");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Change password">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Current password">
          <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label="New password" hint="At least 8 characters. Other devices will be logged out.">
          <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
      </div>
      <ErrorBox message={error} />
      <div className="mt-3 flex items-center gap-3">
        <Button onClick={save} disabled={!current || next.length < 8}>
          Change password
        </Button>
        {done && <span className="text-sm text-green-700">Password changed ✓</span>}
      </div>
    </Card>
  );
}
