"use client";

import Link from "next/link";

import { PageHeader } from "@/components/ui";

const LINKS = [
  { href: "/dashboard/rates", title: "Rent rates", desc: "Default rent per room category & sharing" },
  { href: "/dashboard/messages", title: "WhatsApp", desc: "Connection, QR code, send reminders, message log" },
  { href: "/dashboard/site", title: "Website", desc: "Edit public content, photos & videos" },
  { href: "/dashboard/activity", title: "Activity log", desc: "Every change, who made it and when" },
  { href: "/dashboard/settings", title: "Settings", desc: "Owner WhatsApp, payment note, password, log out" },
];

export default function MorePage() {
  return (
    <div>
      <PageHeader title="More" />
      <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
        {LINKS.map((l) => (
          <li key={l.href}>
            <Link href={l.href} className="flex items-center justify-between px-4 py-3.5 hover:bg-slate-50">
              <div>
                <div className="font-medium">{l.title}</div>
                <div className="text-sm text-slate-500">{l.desc}</div>
              </div>
              <span className="text-slate-400">›</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
