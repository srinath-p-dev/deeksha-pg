"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { inr, monthLabel, todayIST } from "@/lib/format";
import type { PaymentMode, RentRecord } from "@/lib/types";

import { Button, ErrorBox, Field, Input, Modal, Tabs } from "./ui";

export type PayTarget = { record: RentRecord; tenantName: string };

/** Record a (full or partial) payment against one month's rent. */
export function PaymentModal({ target, onClose, onSaved }: { target: PayTarget | null; onClose: () => void; onSaved: () => void }) {
  return (
    <Modal open={!!target} title="Record payment" onClose={onClose}>
      {target && <PaymentForm key={target.record.id} target={target} onSaved={onSaved} />}
    </Modal>
  );
}

function PaymentForm({ target, onSaved }: { target: PayTarget; onSaved: () => void }) {
  const { record, tenantName } = target;
  const [amount, setAmount] = useState(String(record.balance));
  const [paidOn, setPaidOn] = useState(todayIST());
  const [mode, setMode] = useState<PaymentMode>("upi");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api("/api/payments", {
        body: { rent_record_id: record.id, amount: Number(amount), paid_on: paidOn, mode, reference, note },
      });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg bg-slate-50 p-3 text-sm">
        <div className="font-medium">{tenantName}</div>
        <div className="text-slate-600">
          {monthLabel(record.month)} · Due {inr(record.amount_due)} · Paid {inr(record.amount_paid)} ·{" "}
          <span className="font-semibold text-red-600">Balance {inr(record.balance)}</span>
        </div>
      </div>
      <Field label="Amount (₹)">
        <Input type="number" inputMode="numeric" min={1} max={record.balance} value={amount} onChange={(e) => setAmount(e.target.value)} />
      </Field>
      <Field label="Mode">
        <Tabs<PaymentMode>
          value={mode}
          onChange={setMode}
          options={[
            { value: "upi", label: "UPI" },
            { value: "cash", label: "Cash" },
            { value: "bank", label: "Bank" },
          ]}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Paid on">
          <Input type="date" value={paidOn} onChange={(e) => setPaidOn(e.target.value)} />
        </Field>
        <Field label="Reference (optional)">
          <Input value={reference} placeholder="UPI txn id" onChange={(e) => setReference(e.target.value)} />
        </Field>
      </div>
      <Field label="Note (optional)">
        <Input value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <ErrorBox message={error} />
      <Button className="w-full" onClick={save} disabled={saving || !Number(amount)}>
        {saving ? "Saving…" : `Save payment ${amount ? inr(Number(amount)) : ""}`}
      </Button>
    </div>
  );
}
