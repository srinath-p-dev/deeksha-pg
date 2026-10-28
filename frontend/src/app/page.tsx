// Public home page — a Server Component: data is fetched on the server and
// the visitor's browser just receives ready HTML (fast, and good for Google).
import Link from "next/link";

import { GalleryGrid } from "@/components/public/GalleryGrid";
import { PublicShell, Section, whatsappLink } from "@/components/public/PublicShell";
import { inr, sharingLabel } from "@/lib/format";
import { getPublicSite, siteMetadata } from "@/lib/site";

export const generateMetadata = () => siteMetadata();

export default async function Home() {
  const site = await getPublicSite();
  if (!site) {
    return (
      <main className="flex flex-1 items-center justify-center p-6 text-center">
        <div>
          <h1 className="text-2xl font-bold">Website unavailable</h1>
          <p className="mt-2 text-slate-600">Our website is being updated. Please check back soon.</p>
        </div>
      </main>
    );
  }

  const { content: c, prices, gallery } = site;
  const hero = gallery.find((g) => g.kind === "photo" && g.media_url);
  const wa = whatsappLink(c);
  const mapQuery = encodeURIComponent(c.address || c.pg_name);

  return (
    <PublicShell content={c}>
      {/* Hero */}
      <section className="relative overflow-hidden bg-gradient-to-br from-rose-600 to-rose-800 text-white">
        {hero?.media_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={hero.media_url} alt="" className="absolute inset-0 h-full w-full object-cover opacity-30" />
        )}
        <div className="relative mx-auto max-w-5xl px-4 py-20 sm:py-28">
          {c.who_can_stay && <span className="rounded-full bg-white/20 px-3 py-1 text-sm font-medium">{c.who_can_stay} PG</span>}
          <h1 className="mt-4 text-4xl font-extrabold sm:text-5xl">{c.pg_name}</h1>
          {c.tagline && <p className="mt-3 max-w-xl text-lg text-rose-50">{c.tagline}</p>}
          <div className="mt-8 flex flex-wrap gap-3">
            {c.phone && (
              <a href={`tel:${c.phone}`} className="rounded-lg bg-white px-5 py-3 font-semibold text-rose-700 hover:bg-rose-50">
                📞 Call {c.phone}
              </a>
            )}
            {wa && (
              <a href={wa} target="_blank" rel="noreferrer" className="rounded-lg bg-green-500 px-5 py-3 font-semibold text-white hover:bg-green-600">
                WhatsApp us
              </a>
            )}
          </div>
        </div>
      </section>

      {c.about && (
        <Section title="About us">
          <p className="max-w-3xl whitespace-pre-line text-slate-700">{c.about}</p>
        </Section>
      )}

      {prices.length > 0 && (
        <Section id="rooms" title="Rooms & monthly rent" tint>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {prices.map((p) => (
              <div key={p.name} className="rounded-xl border border-rose-100 bg-white p-5 shadow-sm">
                <h3 className="font-semibold">{p.name}</h3>
                {p.description && <p className="text-sm text-slate-500">{p.description}</p>}
                {p.rates.length ? (
                  <ul className="mt-3 space-y-1">
                    {p.rates.map((r) => (
                      <li key={r.sharing} className="flex justify-between text-sm">
                        <span>{sharingLabel(r.sharing)} sharing</span>
                        <span className="font-semibold">{inr(r.monthly_rent)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm text-slate-600">Price on request — up to {p.max_sharing}-sharing.</p>
                )}
              </div>
            ))}
          </div>
          <p className="mt-4 text-sm text-slate-500">Rent is per person per month{c.food ? ", food included" : ""}. Security deposit applies.</p>
        </Section>
      )}

      {(c.amenities.length > 0 || c.food) && (
        <Section title="Amenities & food">
          {c.food && <p className="mb-5 max-w-3xl whitespace-pre-line rounded-xl bg-amber-50 p-4 text-slate-800">🍲 {c.food}</p>}
          {c.amenities.length > 0 && (
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
              {c.amenities.map((a) => (
                <li key={a} className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
                  ✓ {a}
                </li>
              ))}
            </ul>
          )}
        </Section>
      )}

      {gallery.length > 0 && (
        <Section title="Gallery" tint>
          <GalleryGrid items={gallery.slice(0, 6)} />
          {gallery.length > 6 && (
            <Link href="/gallery" className="mt-4 inline-block font-medium text-rose-700">
              See all {gallery.length} photos & videos →
            </Link>
          )}
        </Section>
      )}

      <Section id="location" title="Location">
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-3">
            <p className="whitespace-pre-line text-slate-700">{c.address}</p>
            {c.maps_link && (
              <a href={c.maps_link} target="_blank" rel="noreferrer" className="inline-block rounded-lg bg-rose-600 px-4 py-2 font-medium text-white">
                Open in Google Maps
              </a>
            )}
            {c.phone && (
              <p>
                Call us: <a href={`tel:${c.phone}`} className="font-semibold text-rose-700">{c.phone}</a>
              </p>
            )}
          </div>
          <iframe
            title="Map"
            src={`https://www.google.com/maps?q=${mapQuery}&output=embed`}
            className="h-72 w-full rounded-xl border-0"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
          />
        </div>
      </Section>

      {c.rules.length > 0 && (
        <Section title="House rules" tint>
          <ul className="list-inside list-disc space-y-1 text-slate-700">
            {c.rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </Section>
      )}
    </PublicShell>
  );
}
