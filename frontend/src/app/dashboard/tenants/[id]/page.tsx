"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { PaymentModal, type PayTarget } from "@/components/PaymentModal";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, LinkButton, Loading, Modal, Select, Textarea } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { fdate, fdatetime, inr, monthLabel, phone, sharingLabel, shiftMonth, monthKey, todayIST } from "@/lib/format";
import type { Audit, RentRecord, TenantDetail } from "@/lib/types";

const DOC_KIND: Record<string, string> = { id_proof: "ID proof", photo: "Photo", other: "Other" };

export default function TenantPage() {
  const { id } = useParams<{ id: string }>();
  const { data: t, error, reload } = useApi<TenantDetail>(`/api/tenants/${id}`);
  const activity = useApi<Audit[]>(`/api/audit?entity_type=tenant&entity_id=${id}&limit=20`);
  const [pay, setPay] = useState<PayTarget | null>(null);
  const [modal, setModal] = useState<null | "notice" | "settle" | "delete" | "addMonth">(null);

  if (error) return <ErrorBox message={error} />;
  if (!t) return <Loading />;

  const refresh = () => {
    reload();
    activity.reload();
  };
  const photo = t.documents.find((d) => d.kind === "photo");
  const staying = t.status !== "vacated";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {photo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`/api/tenants/${t.id}/documents/${photo.id}`} alt="" className="h-16 w-16 rounded-full object-cover" />
          ) : (
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-rose-100 text-2xl font-bold text-rose-700">{t.name[0]}</div>
          )}
          <div>
            <h1 className="text-2xl font-bold">{t.name}</h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
              <Badge kind={t.status} />
              Room {t.room_number} · {sharingLabel(t.sharing)} sharing
            </div>
            <div className="mt-1 flex gap-3 text-sm">
              <a href={`tel:+${t.phone}`} className="text-rose-700">
                📞 {phone(t.phone)}
              </a>
              <a href={`https://wa.me/${t.phone}`} target="_blank" rel="noreferrer" className="text-green-700">
                WhatsApp
              </a>
            </div>
          </div>
        </div>
        <LinkButton href={`/dashboard/tenants/${t.id}/edit`} variant="secondary">
          Edit
        </LinkButton>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <div className="text-sm text-slate-500">Monthly rent</div>
          <div className="text-xl font-bold">
            {inr(t.rent)} {t.rent_override !== null && <Badge kind="custom">custom</Badge>}
          </div>
          {t.rent_override !== null && <div className="text-xs text-slate-500">Default {inr(t.default_rent)}</div>}
          <div className="text-xs text-slate-500">{t.category_name}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">Outstanding rent</div>
          <div className={`text-xl font-bold ${t.outstanding ? "text-red-600" : "text-green-700"}`}>{inr(t.outstanding)}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">Deposit</div>
          <div className="text-xl font-bold">{inr(t.deposit_amount)}</div>
          {t.deposit_balance > 0 ? (
            <div className="text-xs font-medium text-amber-700">
              Collected {inr(t.deposit_collected)} · {inr(t.deposit_balance)} pending
            </div>
          ) : (
            <div className="text-xs text-green-700">Fully collected</div>
          )}
        </Card>
      </div>

      <RentHistory tenant={t} onPay={(r) => setPay({ record: r, tenantName: t.name })} onChanged={refresh} onAddMonth={() => setModal("addMonth")} />

      <Documents tenant={t} onChanged={refresh} />

      <Card title="Details">
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <Item label="Joining date" value={fdate(t.joining_date)} />
          <Item label="Biometric no." value={t.biometric_no || "—"} />
          <Item label="Office address" value={t.office_address || "—"} />
          <Item label="Permanent address" value={t.permanent_address || "—"} />
          {t.notice_date && <Item label="Notice given" value={fdate(t.notice_date)} />}
          {t.move_out_date && <Item label="Move-out date" value={fdate(t.move_out_date)} />}
          {t.notes && <Item label="Notes" value={t.notes} />}
        </dl>
      </Card>

      {t.settlement && (
        <Card title="Final settlement">
          <dl className="space-y-1 text-sm">
            <Row label="Moved out" value={fdate(t.settlement.move_out_date)} />
            <Row label="Deposit collected" value={inr(t.settlement.deposit_collected)} />
            <Row label="Pending dues" value={`−${inr(t.settlement.pending_dues)}`} />
            {t.settlement.deductions.map((d, i) => (
              <Row key={i} label={d.reason} value={`−${inr(d.amount)}`} />
            ))}
            <div className="border-t pt-1">
              <Row
                label={t.settlement.refund_amount >= 0 ? "Refunded" : "Tenant owes"}
                value={<b>{inr(Math.abs(t.settlement.refund_amount))}</b>}
              />
            </div>
            {t.settlement.notes && <p className="text-slate-600">{t.settlement.notes}</p>}
          </dl>
        </Card>
      )}

      <Card title="Actions">
        <div className="flex flex-wrap gap-2">
          {t.status === "active" && (
            <Button variant="secondary" onClick={() => setModal("notice")}>
              Give notice
            </Button>
          )}
          {staying && (
            <Button variant="secondary" onClick={() => setModal("settle")}>
              Move out & settle deposit
            </Button>
          )}
          <Button variant="danger" onClick={() => setModal("delete")}>
            Delete permanently
          </Button>
        </div>
      </Card>

      <Card title="History">
        {!activity.data?.length ? (
          <Empty>No changes recorded</Empty>
        ) : (
          <ul className="space-y-3">
            {activity.data.map((a) => (
              <li key={a.id} className="text-sm">
                <div className="whitespace-pre-line text-slate-800">{a.summary.replace(/\*/g, "")}</div>
                <div className="text-xs text-slate-500">
                  {a.actor_name} · {fdatetime(a.created_at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <PaymentModal
        target={pay}
        onClose={() => setPay(null)}
        onSaved={() => {
          setPay(null);
          refresh();
        }}
      />
      <NoticeModal open={modal === "notice"} tenant={t} onClose={() => setModal(null)} onDone={refresh} />
      <SettleModal open={modal === "settle"} tenant={t} onClose={() => setModal(null)} onDone={refresh} />
      <DeleteModal open={modal === "delete"} tenant={t} onClose={() => setModal(null)} />
      <AddMonthModal open={modal === "addMonth"} tenant={t} onClose={() => setModal(null)} onDone={refresh} />
    </div>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-500">{label}</dt>
      <dd className="whitespace-pre-line text-slate-900">{value}</dd>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-600">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function RentHistory({
  tenant,
  onPay,
  onChanged,
  onAddMonth,
}: {
  tenant: TenantDetail;
  onPay: (r: RentRecord) => void;
  onChanged: () => void;
  onAddMonth: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  async function editDue(r: RentRecord) {
    const value = window.prompt(`Amount due for ${monthLabel(r.month)} (₹)`, String(r.amount_due));
    if (value === null || value.trim() === "" || Number(value) === r.amount_due) return;
    try {
      await api(`/api/rent-records/${r.id}`, { method: "PATCH", body: { amount_due: Number(value) } });
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function removePayment(paymentId: number, amount: number) {
    if (!window.confirm(`Remove this payment of ${inr(amount)}?`)) return;
    try {
      await api(`/api/payments/${paymentId}`, { method: "DELETE" });
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card
      title="Rent history"
      actions={
        <Button small variant="secondary" onClick={onAddMonth}>
          + Add month
        </Button>
      }
    >
      <ErrorBox message={error} />
      {tenant.rent_records.length === 0 ? (
        <Empty>No rent records yet</Empty>
      ) : (
        <ul className="divide-y divide-slate-100">
          {tenant.rent_records.map((r) => (
            <li key={r.id} className="py-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">
                    {monthLabel(r.month)} <Badge kind={r.status} />
                  </div>
                  <div className="text-sm text-slate-600">
                    Due{" "}
                    <button className="underline decoration-dotted" onClick={() => editDue(r)} title="Edit amount due">
                      {inr(r.amount_due)}
                    </button>{" "}
                    · Paid {inr(r.amount_paid)}
                    {r.balance > 0 && <span className="font-semibold text-red-600"> · Balance {inr(r.balance)}</span>}
                  </div>
                </div>
                {r.balance > 0 && (
                  <Button small onClick={() => onPay(r)}>
                    Pay
                  </Button>
                )}
              </div>
              {r.payments.length > 0 && (
                <ul className="mt-2 space-y-1 border-l-2 border-slate-200 pl-3 text-xs text-slate-600">
                  {r.payments.map((p) => (
                    <li key={p.id} className="flex items-center justify-between gap-2">
                      <span>
                        {fdate(p.paid_on)} · {inr(p.amount)} · {p.mode.toUpperCase()}
                        {p.reference && ` · ${p.reference}`}
                        {p.note && ` · ${p.note}`}
                      </span>
                      <button className="text-red-600 hover:underline" onClick={() => removePayment(p.id, p.amount)}>
                        remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Documents({ tenant, onChanged }: { tenant: TenantDetail; onChanged: () => void }) {
  const [kind, setKind] = useState("id_proof");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);
    try {
      await api(`/api/tenants/${tenant.id}/documents`, { form });
      setFile(null);
      setInputKey((k) => k + 1);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(docId: number, name: string) {
    if (!window.confirm(`Delete ${name}?`)) return;
    await api(`/api/tenants/${tenant.id}/documents/${docId}`, { method: "DELETE" }).catch((e: Error) => setError(e.message));
    onChanged();
  }

  return (
    <Card title="Documents">
      {tenant.documents.length > 0 && (
        <ul className="mb-3 divide-y divide-slate-100">
          {tenant.documents.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2 py-2 text-sm">
              <a href={`/api/tenants/${tenant.id}/documents/${d.id}`} target="_blank" rel="noreferrer" className="min-w-0 truncate text-rose-700 hover:underline">
                {DOC_KIND[d.kind]}: {d.original_name}
              </a>
              <button className="shrink-0 text-xs text-red-600 hover:underline" onClick={() => remove(d.id, d.original_name)}>
                delete
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex flex-col gap-2 sm:flex-row">
        <Select value={kind} onChange={(e) => setKind(e.target.value)} className="sm:w-40">
          <option value="id_proof">ID proof</option>
          <option value="photo">Photo</option>
          <option value="other">Other</option>
        </Select>
        <Input key={inputKey} type="file" accept="image/*,application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <Button onClick={upload} disabled={!file || busy}>
          {busy ? "Uploading…" : "Upload"}
        </Button>
      </div>
      <p className="mt-1 text-xs text-slate-500">JPG, PNG, WEBP or PDF, up to 10 MB. Stored privately — only logged-in staff can view.</p>
      <ErrorBox message={error} />
    </Card>
  );
}

function NoticeModal({ open, tenant, onClose, onDone }: { open: boolean; tenant: TenantDetail; onClose: () => void; onDone: () => void }) {
  const [noticeDate, setNoticeDate] = useState(todayIST());
  const [moveOut, setMoveOut] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function save() {
    try {
      await api(`/api/tenants/${tenant.id}/notice`, { body: { notice_date: noticeDate, move_out_date: moveOut || null } });
      onClose();
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Modal open={open} title={`Notice — ${tenant.name}`} onClose={onClose}>
      <div className="space-y-3">
        <Field label="Notice date">
          <Input type="date" value={noticeDate} onChange={(e) => setNoticeDate(e.target.value)} />
        </Field>
        <Field label="Planned move-out date">
          <Input type="date" value={moveOut} onChange={(e) => setMoveOut(e.target.value)} />
        </Field>
        <ErrorBox message={error} />
        <Button className="w-full" onClick={save}>
          Mark as on notice
        </Button>
      </div>
    </Modal>
  );
}

function SettleModal({ open, tenant, onClose, onDone }: { open: boolean; tenant: TenantDetail; onClose: () => void; onDone: () => void }) {
  const preview = useApi<{ deposit_collected: number; pending_dues: number; dues_by_month: { month: string; balance: number }[] }>(
    open ? `/api/tenants/${tenant.id}/settlement/preview` : null,
  );
  const [moveOut, setMoveOut] = useState(tenant.move_out_date ?? todayIST());
  const [deductions, setDeductions] = useState<{ reason: string; amount: string }[]>([]);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const p = preview.data;
  const totalDeductions = deductions.reduce((s, d) => s + (Number(d.amount) || 0), 0);
  const refund = p ? p.deposit_collected - p.pending_dues - totalDeductions : 0;

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api(`/api/tenants/${tenant.id}/settlement`, {
        body: {
          move_out_date: moveOut,
          notes,
          deductions: deductions.filter((d) => d.reason.trim()).map((d) => ({ reason: d.reason, amount: Number(d.amount) || 0 })),
        },
      });
      onClose();
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} title={`Move out — ${tenant.name}`} onClose={onClose}>
      {!p ? (
        <Loading />
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            Tip: if the last month should be prorated, edit that month&apos;s &quot;Due&quot; amount in Rent history first.
          </p>
          <Field label="Move-out date">
            <Input type="date" value={moveOut} onChange={(e) => setMoveOut(e.target.value)} />
          </Field>
          <div className="space-y-1 rounded-lg bg-slate-50 p-3 text-sm">
            <Row label="Deposit collected" value={inr(p.deposit_collected)} />
            {p.dues_by_month.map((d) => (
              <Row key={d.month} label={`Rent due ${monthLabel(d.month)}`} value={`−${inr(d.balance)}`} />
            ))}
            {deductions.map((d, i) => d.reason && <Row key={i} label={d.reason} value={`−${inr(Number(d.amount) || 0)}`} />)}
            <div className="border-t pt-1 font-semibold">
              <Row label={refund >= 0 ? "Refund to tenant" : "Tenant still owes"} value={inr(Math.abs(refund))} />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">Deductions</div>
            {deductions.map((d, i) => (
              <div key={i} className="flex gap-2">
                <Input
                  placeholder="Reason (e.g. painting)"
                  value={d.reason}
                  onChange={(e) => setDeductions((all) => all.map((x, j) => (j === i ? { ...x, reason: e.target.value } : x)))}
                />
                <Input
                  className="w-28"
                  type="number"
                  inputMode="numeric"
                  placeholder="₹"
                  value={d.amount}
                  onChange={(e) => setDeductions((all) => all.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))}
                />
                <Button small variant="ghost" onClick={() => setDeductions((all) => all.filter((_, j) => j !== i))}>
                  ✕
                </Button>
              </div>
            ))}
            <Button small variant="secondary" onClick={() => setDeductions((all) => [...all, { reason: "", amount: "" }])}>
              + Add deduction
            </Button>
          </div>
          <Field label="Notes">
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          <ErrorBox message={error} />
          <Button className="w-full" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Confirm move-out & settlement"}
          </Button>
        </div>
      )}
    </Modal>
  );
}

function DeleteModal({ open, tenant, onClose }: { open: boolean; tenant: TenantDetail; onClose: () => void }) {
  const router = useRouter();
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    try {
      await api(`/api/tenants/${tenant.id}?confirm_name=${encodeURIComponent(typed)}`, { method: "DELETE" });
      router.push("/dashboard/tenants");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Modal open={open} title="Delete permanently?" onClose={onClose}>
      <div className="space-y-3 text-sm">
        <p>
          This removes <b>{tenant.name}</b> and all their rent history, payments and documents. It can&apos;t be undone.
        </p>
        <p className="text-slate-600">If they&apos;re just leaving, use &quot;Move out &amp; settle&quot; instead — it keeps their history.</p>
        <Field label={`Type "${tenant.name}" to confirm`}>
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} />
        </Field>
        <ErrorBox message={error} />
        <Button variant="danger" className="w-full" disabled={typed.trim() !== tenant.name} onClick={remove}>
          Delete forever
        </Button>
      </div>
    </Modal>
  );
}

function AddMonthModal({ open, tenant, onClose, onDone }: { open: boolean; tenant: TenantDetail; onClose: () => void; onDone: () => void }) {
  const [month, setMonth] = useState(shiftMonth(monthKey(todayIST()), -1));
  const [amount, setAmount] = useState(String(tenant.rent ?? ""));
  const [error, setError] = useState<string | null>(null);

  async function save() {
    try {
      await api(`/api/tenants/${tenant.id}/rent-records`, { body: { month, amount_due: Number(amount) } });
      onClose();
      onDone();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Modal open={open} title="Add a month's rent" onClose={onClose}>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">Use this for older unpaid months (e.g. when adding an existing tenant). New months are created automatically on the 1st.</p>
        <Field label="Month">
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        </Field>
        <Field label="Amount due (₹)">
          <Input type="number" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
        <ErrorBox message={error} />
        <Button className="w-full" onClick={save}>
          Add
        </Button>
      </div>
    </Modal>
  );
}
