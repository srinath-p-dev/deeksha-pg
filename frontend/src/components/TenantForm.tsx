"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { api, useApi } from "@/lib/api";
import { daysInMonth, inr, monthKey, sharingLabel, todayIST } from "@/lib/format";
import type { Category, Room, TenantDetail } from "@/lib/types";

import { Button, Card, ErrorBox, Field, Input, Loading, Select, Textarea } from "./ui";

type Form = {
  name: string;
  phone: string;
  room_id: string;
  sharing: string;
  customRent: boolean;
  rent_override: string;
  deposit_amount: string;
  deposit_collected: string;
  joining_date: string;
  biometric_no: string;
  office_address: string;
  permanent_address: string;
  notes: string;
};

const num = (s: string) => (s.trim() === "" ? null : Number(s));

function initialForm(t?: TenantDetail): Form {
  return {
    name: t?.name ?? "",
    phone: t ? t.phone.replace(/^91/, "") : "",
    room_id: t ? String(t.room_id) : "",
    sharing: t ? String(t.sharing) : "",
    customRent: t ? t.rent_override !== null : false,
    rent_override: t?.rent_override != null ? String(t.rent_override) : "",
    deposit_amount: t ? String(t.deposit_amount) : "",
    deposit_collected: t ? String(t.deposit_collected) : "",
    joining_date: t?.joining_date ?? todayIST(),
    biometric_no: t?.biometric_no ?? "",
    office_address: t?.office_address ?? "",
    permanent_address: t?.permanent_address ?? "",
    notes: t?.notes ?? "",
  };
}

/** Add or edit a tenant. Rent auto-fills from the room's category + sharing type. */
export function TenantForm({ tenant }: { tenant?: TenantDetail }) {
  const router = useRouter();
  const rooms = useApi<Room[]>("/api/rooms");
  const categories = useApi<Category[]>("/api/categories");
  const [f, setF] = useState<Form>(() => initialForm(tenant));
  const [firstMonthManual, setFirstMonthManual] = useState(false);
  const [firstMonthRent, setFirstMonthRent] = useState("");
  const [thisMonthManual, setThisMonthManual] = useState(false);
  const [thisMonthDue, setThisMonthDue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setF((prev) => ({ ...prev, [key]: value }));

  const room = rooms.data?.find((r) => String(r.id) === f.room_id);
  const category = categories.data?.find((c) => c.id === room?.category_id);
  const sharing = Number(f.sharing) || 0;
  const defaultRent = category?.rates.find((r) => r.sharing === sharing)?.monthly_rent ?? null;
  const effectiveRent = f.customRent ? num(f.rent_override) : defaultRent;

  const today = todayIST();
  const isEdit = !!tenant;
  const placementChanged = isEdit && (f.room_id !== String(tenant.room_id) || f.sharing !== String(tenant.sharing));
  const rentChanged = isEdit && tenant.status !== "vacated" && effectiveRent !== null && effectiveRent !== tenant.rent;
  const currentRecord = tenant?.rent_records.find((r) => monthKey(r.month) === monthKey(today));

  // Suggested prorated amounts (the server computes the same if left automatic)
  const remaining = daysInMonth(today) - Number(today.slice(8)) + 1;
  const proratedThisMonth =
    currentRecord && tenant?.rent != null && effectiveRent != null
      ? currentRecord.amount_due + Math.round(((effectiveRent - tenant.rent) * remaining) / daysInMonth(today))
      : null;
  const joinsThisMonth = monthKey(f.joining_date) === monthKey(today);
  const firstMonthSuggested =
    effectiveRent != null && joinsThisMonth
      ? Math.round((effectiveRent * (daysInMonth(f.joining_date) - Number(f.joining_date.slice(8)) + 1)) / daysInMonth(f.joining_date))
      : effectiveRent;

  const roomOptions = useMemo(
    () =>
      (rooms.data ?? [])
        .filter((r) => r.is_active || String(r.id) === f.room_id)
        .map((r) => {
          const others = r.occupants.filter((o) => o.id !== tenant?.id);
          const capacity = Math.min(r.max_sharing, ...others.map((o) => o.sharing));
          const full = others.length >= capacity;
          return { r, label: `${r.number} · ${r.category_name} · ${others.length}/${capacity}${full ? " (full)" : ""}`, full };
        }),
    [rooms.data, f.room_id, tenant?.id],
  );

  if (rooms.error || categories.error) return <ErrorBox message={rooms.error ?? categories.error} />;
  if (!rooms.data || !categories.data) return <Loading />;

  async function save() {
    setSaving(true);
    setError(null);
    const payload: Record<string, unknown> = {
      name: f.name,
      phone: f.phone,
      room_id: Number(f.room_id),
      sharing,
      rent_override: f.customRent ? num(f.rent_override) : null,
      deposit_amount: num(f.deposit_amount) ?? 0,
      deposit_collected: num(f.deposit_collected),
      joining_date: f.joining_date,
      biometric_no: f.biometric_no,
      office_address: f.office_address,
      permanent_address: f.permanent_address,
      notes: f.notes,
    };
    try {
      if (!isEdit) {
        if (firstMonthManual) payload.first_month_rent = num(firstMonthRent);
        const created = await api<TenantDetail>("/api/tenants", { body: payload });
        router.push(`/dashboard/tenants/${created.id}`);
      } else {
        // Only send fields that changed, so the change message is accurate
        const before = initialForm(tenant);
        const changed: Record<string, unknown> = {};
        for (const [key, value] of Object.entries(payload)) {
          const formKey = key as keyof Form;
          const prev =
            key === "rent_override"
              ? before.customRent
                ? num(before.rent_override)
                : null
              : key === "room_id" || key === "sharing" || key === "deposit_amount" || key === "deposit_collected"
                ? num(String(before[formKey]))
                : before[formKey];
          if (prev !== value) changed[key] = value;
        }
        if (rentChanged && currentRecord && thisMonthManual) changed.current_month_due = num(thisMonthDue);
        await api(`/api/tenants/${tenant.id}`, { method: "PATCH", body: changed });
        router.push(`/dashboard/tenants/${tenant.id}`);
      }
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  }

  const maxSharing = room?.max_sharing ?? 3;

  return (
    <div className="space-y-4">
      <Card title="Personal details">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Full name">
            <Input value={f.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="WhatsApp number" hint="10-digit mobile number">
            <Input type="tel" inputMode="tel" value={f.phone} onChange={(e) => set("phone", e.target.value)} />
          </Field>
          <Field label="Biometric number">
            <Input value={f.biometric_no} onChange={(e) => set("biometric_no", e.target.value)} />
          </Field>
          <Field label="Joining date">
            <Input type="date" value={f.joining_date} onChange={(e) => set("joining_date", e.target.value)} />
          </Field>
          <Field label="Office address" className="sm:col-span-2">
            <Textarea value={f.office_address} onChange={(e) => set("office_address", e.target.value)} />
          </Field>
          <Field label="Permanent address" className="sm:col-span-2">
            <Textarea value={f.permanent_address} onChange={(e) => set("permanent_address", e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card title="Room & rent">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Room">
            <Select value={f.room_id} onChange={(e) => set("room_id", e.target.value)}>
              <option value="">Select room…</option>
              {roomOptions.map(({ r, label, full }) => (
                <option key={r.id} value={r.id} disabled={full && String(r.id) !== String(tenant?.room_id)}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Sharing type">
            <Select value={f.sharing} onChange={(e) => set("sharing", e.target.value)}>
              <option value="">Select…</option>
              {Array.from({ length: maxSharing }, (_, i) => i + 1).map((s) => {
                const rate = category?.rates.find((r) => r.sharing === s)?.monthly_rent;
                return (
                  <option key={s} value={s}>
                    {sharingLabel(s)} {rate != null ? `— ${inr(rate)}` : "— no default rent"}
                  </option>
                );
              })}
            </Select>
          </Field>
        </div>

        <div className="mt-4 rounded-lg bg-slate-50 p-3">
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="text-sm text-slate-600">Monthly rent</div>
              <div className="text-xl font-bold">
                {inr(effectiveRent)}
                {f.customRent && <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">custom</span>}
              </div>
              {f.customRent && defaultRent !== null && <div className="text-xs text-slate-500">Default for this room/sharing: {inr(defaultRent)}</div>}
              {!f.customRent && room && sharing > 0 && defaultRent === null && (
                <div className="text-xs text-red-600">No default rent for this room/sharing — enter a custom rent.</div>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={f.customRent} onChange={(e) => set("customRent", e.target.checked)} />
              Custom rent
            </label>
          </div>
          {f.customRent && (
            <Field label="Custom monthly rent (₹)" className="mt-3">
              <Input type="number" inputMode="numeric" value={f.rent_override} onChange={(e) => set("rent_override", e.target.value)} />
            </Field>
          )}
          {isEdit && placementChanged && tenant.rent_override !== null && (
            <div className="mt-3 rounded-lg border border-violet-200 bg-violet-50 p-3 text-sm">
              This tenant has a custom rent of {inr(tenant.rent_override)}. Keep it, or use the new default{" "}
              {defaultRent !== null ? inr(defaultRent) : "(none set)"}?
              <div className="mt-2 flex gap-2">
                <Button small variant={f.customRent ? "primary" : "secondary"} onClick={() => setF((p) => ({ ...p, customRent: true, rent_override: String(tenant.rent_override) }))}>
                  Keep {inr(tenant.rent_override)}
                </Button>
                <Button small variant={!f.customRent ? "primary" : "secondary"} disabled={defaultRent === null} onClick={() => set("customRent", false)}>
                  Use default
                </Button>
              </div>
            </div>
          )}
        </div>

        {!isEdit && joinsThisMonth && (
          <div className="mt-3 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={firstMonthManual} onChange={(e) => setFirstMonthManual(e.target.checked)} />
              Set first month&apos;s rent manually (default: {inr(firstMonthSuggested)} for the remaining days)
            </label>
            {firstMonthManual && <Input className="mt-2" type="number" inputMode="numeric" placeholder="First month rent" value={firstMonthRent} onChange={(e) => setFirstMonthRent(e.target.value)} />}
          </div>
        )}

        {rentChanged && currentRecord && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
            Rent changes from {inr(tenant.rent)} to {inr(effectiveRent)}. This month&apos;s due is {inr(currentRecord.amount_due)}.
            <label className="mt-2 flex items-center gap-2">
              <input type="radio" checked={!thisMonthManual} onChange={() => setThisMonthManual(false)} />
              Prorate from today → {inr(proratedThisMonth)}
            </label>
            <label className="mt-1 flex items-center gap-2">
              <input type="radio" checked={thisMonthManual} onChange={() => setThisMonthManual(true)} />
              Set this month&apos;s due manually
            </label>
            {thisMonthManual && <Input className="mt-2" type="number" inputMode="numeric" value={thisMonthDue} onChange={(e) => setThisMonthDue(e.target.value)} />}
          </div>
        )}
      </Card>

      <Card title="Security deposit">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Deposit amount (₹)">
            <Input type="number" inputMode="numeric" value={f.deposit_amount} onChange={(e) => set("deposit_amount", e.target.value)} />
          </Field>
          <Field label="Deposit collected (₹)" hint={isEdit ? undefined : "Leave empty if paid in full"}>
            <Input type="number" inputMode="numeric" value={f.deposit_collected} placeholder={f.deposit_amount} onChange={(e) => set("deposit_collected", e.target.value)} />
          </Field>
        </div>
      </Card>

      <Card title="Notes">
        <Textarea value={f.notes} onChange={(e) => set("notes", e.target.value)} />
      </Card>

      <ErrorBox message={error} />
      <div className="flex gap-2">
        <Button onClick={save} disabled={saving || !f.name || !f.phone || !f.room_id || !f.sharing}>
          {saving ? "Saving…" : isEdit ? "Save changes" : "Add tenant"}
        </Button>
        <Button variant="secondary" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
