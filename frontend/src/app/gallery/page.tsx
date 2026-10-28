import { GalleryGrid } from "@/components/public/GalleryGrid";
import { PublicShell, Section } from "@/components/public/PublicShell";
import { getPublicSite, siteMetadata } from "@/lib/site";

export const generateMetadata = () => siteMetadata("Gallery");

export default async function GalleryPage() {
  const site = await getPublicSite();
  if (!site) return <p className="p-6 text-center">Gallery unavailable right now.</p>;
  return (
    <PublicShell content={site.content}>
      <Section title="Photos & videos">
        {site.gallery.length ? <GalleryGrid items={site.gallery} /> : <p className="text-slate-500">Photos coming soon.</p>}
      </Section>
    </PublicShell>
  );
}
