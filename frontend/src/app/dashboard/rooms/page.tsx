"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, ErrorBox, Field, Input, Loading, Modal, PageHeader, Select } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { sharingLabel } from "@/lib/format";
import type { Category, Room } from "@/lib/types";

function roomTone(r: Room) {
  if (!r.is_active) return "border-slate-200 bg-slate-100 text-slate-400";
  if (r.occupants.length === 0) return "border-green-300 bg-green-50";
  if (r.occupants.length >= r.capacity_now) return "border-slate-300 bg-white";
  return "border-amber-300 bg-amber-50";
}

export default function RoomsPage() {
  const { data: rooms, error, reload } = useApi<Room[]>("/api/rooms");
  const categories = useApi<Category[]>("/api/categories");
  const [selected, setSelected] = useState<Room | null>(null);

  if (error) return <ErrorBox message={error} />;
  if (!rooms) return <Loading />;

  const floors = [...new Set(rooms.map((r) => r.floor))].sort();

  return (
    <div className="space-y-5">
      <PageHeader
        title="Rooms"
        subtitle={
          <span className="flex flex-wrap gap-3">
            <span>🟩 empty</span>
            <span>🟨 has free bed</span>
            <span>⬜ full</span>
          </span>
        }
      />
      {floors.map((floor) => (
        <section key={floor}>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Floor {floor}</h2>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-5">
            {rooms
              .filter((r) => r.floor === floor)
              .map((r) => (
                <button key={r.id} onClick={() => setSelected(r)} className={`rounded-xl border p-3 text-left ${roomTone(r)}`}>
                  <div className="flex items-baseline justify-between">
                    <span className="text-lg font-bold">{r.number}</span>
                    <span className="text-xs font-medium">
                      {r.occupants.length}/{r.capacity_now}
                    </span>
                  </div>
                  <div className="truncate text-xs text-slate-500">{r.category_name}</div>
                  <div className="mt-1 truncate text-xs">{r.occupants.map((o) => o.name.split(" ")[0]).join(", ") || "—"}</div>
                </button>
              ))}
          </div>
        </section>
      ))}

      <RoomModal
        room={selected}
        categories={categories.data ?? []}
        onClose={() => setSelected(null)}
        onSaved={() => {
          setSelected(null);
          reload();
        }}
      />
    </div>
  );
}

function RoomModal({ room, categories, onClose, onSaved }: { room: Room | null; categories: Category[]; onClose: () => void; onSaved: () => void }) {
  return (
    <Modal open={!!room} title={room ? `Room ${room.number}` : ""} onClose={onClose}>
      {room && <RoomEditor key={room.id} room={room} categories={categories} onSaved={onSaved} />}
    </Modal>
  );
}

function RoomEditor({ room, categories, onSaved }: { room: Room; categories: Category[]; onSaved: () => void }) {
  const [categoryId, setCategoryId] = useState(String(room.category_id));
  const [notes, setNotes] = useState(room.notes);
  const [active, setActive] = useState(room.is_active);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    try {
      await api(`/api/rooms/${room.id}`, { method: "PATCH", body: { category_id: Number(categoryId), notes, is_active: active } });
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <div className="text-sm font-medium">Occupants</div>
        {room.occupants.length === 0 ? (
          <p className="text-sm text-slate-500">Empty</p>
        ) : (
          <ul className="text-sm">
            {room.occupants.map((o) => (
              <li key={o.id}>
                <Link href={`/dashboard/tenants/${o.id}`} className="text-rose-700 hover:underline">
                  {o.name}
                </Link>{" "}
                <span className="text-slate-500">· {sharingLabel(o.sharing)}</span>
              </li>
            ))}
          </ul>
        )}
        <Link href="/dashboard/tenants/new" className="mt-1 inline-block text-sm text-rose-700">
          + Add tenant
        </Link>
      </div>
      <Field label="Category (sets the default rent)">
        <Select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} (up to {c.max_sharing}-sharing)
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Notes">
        <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
        Room is available for tenants
      </label>
      <ErrorBox message={error} />
      <Button className="w-full" onClick={save}>
        Save
      </Button>
    </div>
  );
}
