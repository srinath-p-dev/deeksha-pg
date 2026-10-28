"use client";

import { useState } from "react";

import { Button, Card, ErrorBox, Field, Input, Loading, PageHeader } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { sharingLabel } from "@/lib/format";
import type { Category } from "@/lib/types";

export default function RatesPage() {
  const { data, error, reload } = useApi<Category[]>("/api/categories");
  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  return (
    <div className="space-y-4">
      <PageHeader
        title="Rent rates"
        subtitle="Default monthly rent per room category and sharing type. Leave a box empty to always type the rent manually (e.g. 6th floor)."
      />
      {data.map((c) => (
        <CategoryCard key={c.id} category={c} onSaved={reload} />
      ))}
    </div>
  );
}

function CategoryCard({ category, onSaved }: { category: Category; onSaved: () => void }) {
  const initial = Object.fromEntries(
    Array.from({ length: category.max_sharing }, (_, i) => {
      const s = i + 1;
      const rent = category.rates.find((r) => r.sharing === s)?.monthly_rent;
      return [s, rent != null ? String(rent) : ""];
    }),
  );
  const [values, setValues] = useState<Record<number, string>>(initial);
  const [applyToExisting, setApplyToExisting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const dirty = Object.entries(values).some(([s, v]) => v !== initial[Number(s)]);

  async function save() {
    setError(null);
    try {
      await api(`/api/categories/${category.id}`, {
        method: "PUT",
        body: {
          rates: Object.entries(values).map(([s, v]) => ({ sharing: Number(s), monthly_rent: v.trim() === "" ? null : Number(v) })),
          apply_to_existing: applyToExisting,
        },
      });
      setSaved(true);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title={category.name} actions={<span className="text-xs text-slate-500">{category.room_count} rooms</span>}>
      {category.description && <p className="-mt-2 mb-3 text-sm text-slate-500">{category.description}</p>}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {Object.keys(values).map((s) => (
          <Field key={s} label={sharingLabel(Number(s))}>
            <Input
              type="number"
              inputMode="numeric"
              placeholder="manual"
              value={values[Number(s)]}
              onChange={(e) => {
                setSaved(false);
                setValues((v) => ({ ...v, [Number(s)]: e.target.value }));
              }}
            />
          </Field>
        ))}
      </div>
      {dirty && (
        <label className="mt-3 flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked={applyToExisting} onChange={(e) => setApplyToExisting(e.target.checked)} />
          <span>
            Apply new rates to current tenants too
            <span className="block text-xs text-slate-500">
              If unticked, current tenants keep paying their old rent (saved as their custom rent); only new tenants get the new rate.
            </span>
          </span>
        </label>
      )}
      <ErrorBox message={error} />
      <div className="mt-3 flex items-center gap-3">
        <Button onClick={save} disabled={!dirty}>
          Save rates
        </Button>
        {saved && !dirty && <span className="text-sm text-green-700">Saved ✓</span>}
      </div>
    </Card>
  );
}
