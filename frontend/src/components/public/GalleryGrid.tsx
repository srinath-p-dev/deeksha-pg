import type { GalleryItem } from "@/lib/types";

export function GalleryGrid({ items }: { items: GalleryItem[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      {items.map((item) => (
        <figure key={item.id} className={`overflow-hidden rounded-xl bg-slate-100 ${item.kind !== "photo" ? "col-span-2 md:col-span-1" : ""}`}>
          {item.kind === "photo" && item.media_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.media_url} alt={item.caption || "PG photo"} loading="lazy" className="aspect-[4/3] w-full object-cover" />
          )}
          {item.kind === "video" && item.media_url && (
            <video src={item.media_url} controls preload="metadata" className="aspect-video w-full bg-black" />
          )}
          {item.kind === "video_url" && item.url && (
            <iframe
              src={item.url}
              title={item.caption || "Video"}
              className="aspect-video w-full"
              allow="accelerometer; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              loading="lazy"
            />
          )}
          {item.caption && <figcaption className="px-3 py-2 text-sm text-slate-600">{item.caption}</figcaption>}
        </figure>
      ))}
    </div>
  );
}
