import Link from "next/link";
import type { ReactNode } from "react";

import type { SiteContent } from "@/lib/types";

export function whatsappLink(content: SiteContent) {
  const text = encodeURIComponent(`Hi, I'm interested in a room at ${content.pg_name}.`);
  return content.whatsapp ? `https://wa.me/${content.whatsapp}?text=${text}` : null;
}

export function PublicShell({ content, children }: { content: SiteContent; children: ReactNode }) {
  const wa = whatsappLink(content);
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="sticky top-0 z-30 border-b border-rose-100 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <Link href="/" className="text-lg font-bold text-rose-700">
            {content.pg_name}
          </Link>
          <nav className="flex gap-4 text-sm text-slate-600">
            <Link href="/#rooms">Rooms</Link>
            <Link href="/gallery">Gallery</Link>
            <Link href="/#location">Location</Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <footer className="border-t border-slate-100 bg-slate-50">
        <div className="mx-auto flex max-w-5xl flex-wrap justify-between gap-2 px-4 py-6 text-sm text-slate-500">
          <span>
            © {new Date().getFullYear()} {content.pg_name}
          </span>
          <Link href="/login" className="hover:text-slate-700">
            Owner login
          </Link>
        </div>
      </footer>
      {wa && (
        <a
          href={wa}
          target="_blank"
          rel="noreferrer"
          className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-green-500 px-5 py-3 font-semibold text-white shadow-lg hover:bg-green-600"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden>
            <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm5.3 14.1c-.2.6-1.3 1.2-1.8 1.2-.5.1-1 .1-3.3-.8-2.8-1.1-4.5-3.9-4.7-4.1-.1-.2-1.1-1.5-1.1-2.9s.7-2 1-2.3c.2-.3.5-.3.7-.3h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.3.5-.4.4c-.1.1-.3.3-.1.6.2.3.8 1.3 1.7 2.1 1.2 1 2.1 1.4 2.4 1.5.3.2.5.1.6 0l.9-1c.2-.3.4-.2.6-.1l1.9.9c.3.1.5.2.5.3.1.2.1.7-.1 1.4Z" />
          </svg>
          Chat with us
        </a>
      )}
    </div>
  );
}

export function Section({ id, title, children, tint }: { id?: string; title: string; children: ReactNode; tint?: boolean }) {
  return (
    <section id={id} className={`scroll-mt-16 ${tint ? "bg-rose-50/60" : ""}`}>
      <div className="mx-auto max-w-5xl px-4 py-12">
        <h2 className="mb-6 text-2xl font-bold text-slate-900">{title}</h2>
        {children}
      </div>
    </section>
  );
}
