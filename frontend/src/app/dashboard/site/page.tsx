"use client";

import { useState } from "react";

import { Button, Card, Empty, ErrorBox, Field, Input, LinkButton, Loading, PageHeader, Textarea } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import type { GalleryItem, SiteContent } from "@/lib/types";

export default function SitePage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Website"
        subtitle="What visitors see on the public site."
        actions={
          <LinkButton href="/" variant="secondary">
            View website ↗
          </LinkButton>
        }
      />
      <ContentForm />
      <Gallery />
    </div>
  );
}

function ContentForm() {
  const { data, error } = useApi<SiteContent>("/api/site");
  if (error) return <ErrorBox message={error} />;
  if (!data) return <Loading />;
  return <ContentEditor initial={data} />;
}

function ContentEditor({ initial }: { initial: SiteContent }) {
  const [c, setC] = useState(initial);
  const [amenities, setAmenities] = useState(initial.amenities.join("\n"));
  const [rules, setRules] = useState(initial.rules.join("\n"));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const set = <K extends keyof SiteContent>(k: K, v: SiteContent[K]) => {
    setSaved(false);
    setC((p) => ({ ...p, [k]: v }));
  };

  async function save() {
    setError(null);
    try {
      await api("/api/site", {
        method: "PUT",
        body: { ...c, amenities: amenities.split("\n"), rules: rules.split("\n") },
      });
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <Card title="Content">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="PG name">
          <Input value={c.pg_name} onChange={(e) => set("pg_name", e.target.value)} />
        </Field>
        <Field label="Who can stay">
          <Input value={c.who_can_stay} onChange={(e) => set("who_can_stay", e.target.value)} />
        </Field>
        <Field label="Tagline" className="sm:col-span-2">
          <Input value={c.tagline} onChange={(e) => set("tagline", e.target.value)} />
        </Field>
        <Field label="About" className="sm:col-span-2">
          <Textarea rows={5} value={c.about} onChange={(e) => set("about", e.target.value)} />
        </Field>
        <Field label="Food" className="sm:col-span-2" hint="e.g. Breakfast, lunch & dinner — South & North Indian">
          <Textarea value={c.food} onChange={(e) => set("food", e.target.value)} />
        </Field>
        <Field label="Amenities" hint="One per line">
          <Textarea rows={6} value={amenities} onChange={(e) => (setSaved(false), setAmenities(e.target.value))} />
        </Field>
        <Field label="House rules" hint="One per line">
          <Textarea rows={6} value={rules} onChange={(e) => (setSaved(false), setRules(e.target.value))} />
        </Field>
        <Field label="Address" className="sm:col-span-2">
          <Textarea value={c.address} onChange={(e) => set("address", e.target.value)} />
        </Field>
        <Field label="Google Maps link">
          <Input value={c.maps_link} onChange={(e) => set("maps_link", e.target.value)} />
        </Field>
        <Field label="Contact phone">
          <Input value={c.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field label="WhatsApp number for 'Chat with us'">
          <Input value={c.whatsapp} onChange={(e) => set("whatsapp", e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 self-end pb-3 text-sm">
          <input type="checkbox" checked={c.show_prices} onChange={(e) => set("show_prices", e.target.checked)} />
          Show prices on the website
        </label>
      </div>
      <ErrorBox message={error} />
      <div className="mt-3 flex items-center gap-3">
        <Button onClick={save}>Save content</Button>
        {saved && <span className="text-sm text-green-700">Saved ✓</span>}
      </div>
    </Card>
  );
}

function Gallery() {
  const { data, error, reload } = useApi<GalleryItem[]>("/api/gallery");
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [link, setLink] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [inputKey, setInputKey] = useState(0);

  async function wrap(fn: () => Promise<unknown>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      reload();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const upload = () =>
    wrap(async () => {
      const form = new FormData();
      form.append("file", file!);
      form.append("caption", caption);
      await api("/api/gallery/upload", { form });
      setFile(null);
      setCaption("");
      setInputKey((k) => k + 1);
    });

  const addLink = () =>
    wrap(async () => {
      await api("/api/gallery/link", { body: { url: link, caption } });
      setLink("");
      setCaption("");
    });

  const move = (item: GalleryItem, dir: -1 | 1) =>
    wrap(async () => {
      const items = data ?? [];
      const i = items.findIndex((x) => x.id === item.id);
      const other = items[i + dir];
      if (!other) return;
      await api(`/api/gallery/${item.id}`, { method: "PATCH", body: { sort_order: other.sort_order } });
      await api(`/api/gallery/${other.id}`, { method: "PATCH", body: { sort_order: item.sort_order } });
    });

  const editCaption = (item: GalleryItem) => {
    const value = window.prompt("Caption", item.caption);
    if (value !== null) wrap(() => api(`/api/gallery/${item.id}`, { method: "PATCH", body: { caption: value } }));
  };

  const remove = (item: GalleryItem) => {
    if (window.confirm("Remove from gallery?")) wrap(() => api(`/api/gallery/${item.id}`, { method: "DELETE" }));
  };

  return (
    <Card title="Photos & videos">
      <div className="space-y-2 rounded-lg bg-slate-50 p-3">
        <Input placeholder="Caption (optional)" value={caption} onChange={(e) => setCaption(e.target.value)} />
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input key={inputKey} type="file" accept="image/*,video/mp4,video/webm" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <Button onClick={upload} disabled={!file || busy}>
            Upload
          </Button>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input placeholder="…or paste a YouTube link" value={link} onChange={(e) => setLink(e.target.value)} />
          <Button variant="secondary" onClick={addLink} disabled={!link || busy}>
            Add video link
          </Button>
        </div>
        <p className="text-xs text-slate-500">Photos up to 10 MB (JPG/PNG/WEBP). Videos up to 100 MB (MP4/WEBM) — for longer videos use a YouTube link.</p>
      </div>
      <ErrorBox message={err ?? error} />
      {!data ? (
        <Loading />
      ) : data.length === 0 ? (
        <Empty>No photos yet. The first photo is used as the website&apos;s main image.</Empty>
      ) : (
        <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {data.map((item, i) => (
            <li key={item.id} className="overflow-hidden rounded-lg border border-slate-200 bg-white">
              <div className="aspect-video bg-slate-100">
                {item.kind === "photo" && item.media_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={item.media_url} alt={item.caption} className="h-full w-full object-cover" />
                ) : (
                  <div className="flex h-full items-center justify-center text-3xl">🎬</div>
                )}
              </div>
              <div className="p-2 text-xs">
                <div className="truncate">{item.caption || <span className="text-slate-400">No caption</span>}</div>
                <div className="mt-1 flex gap-2">
                  <button disabled={i === 0} onClick={() => move(item, -1)} className="disabled:opacity-30">
                    ◀
                  </button>
                  <button disabled={i === data.length - 1} onClick={() => move(item, 1)} className="disabled:opacity-30">
                    ▶
                  </button>
                  <button onClick={() => editCaption(item)} className="text-rose-700">
                    caption
                  </button>
                  <button onClick={() => remove(item)} className="ml-auto text-red-600">
                    delete
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
