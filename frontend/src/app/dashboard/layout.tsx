"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Loading } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import type { User, WhatsAppStatus } from "@/lib/types";
import { usePgName } from "@/lib/usePgName";

const NAV = [
  { href: "/dashboard", label: "Home", icon: "🏠" },
  { href: "/dashboard/checklist", label: "Checklist", icon: "✅" },
  { href: "/dashboard/tenants", label: "Tenants", icon: "👩" },
  { href: "/dashboard/rent", label: "Rent", icon: "💵" },
  { href: "/dashboard/rooms", label: "Rooms", icon: "🚪" },
  { href: "/dashboard/more", label: "More", icon: "☰" },
];

const MORE = [
  { href: "/dashboard/rates", label: "Rates" },
  { href: "/dashboard/messages", label: "WhatsApp" },
  { href: "/dashboard/site", label: "Website" },
  { href: "/dashboard/activity", label: "Activity" },
  { href: "/dashboard/settings", label: "Settings" },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (href === "/dashboard/more") return MORE.some((m) => pathname.startsWith(m.href)) || pathname === href;
  return pathname.startsWith(href);
}

/** Polls WhatsApp status every minute and shows a red banner if it's down. */
function WhatsAppBanner() {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  useEffect(() => {
    let alive = true;
    const check = () =>
      api<WhatsAppStatus>("/api/whatsapp/status").then(
        (s) => alive && setStatus(s),
        () => undefined,
      );
    check();
    const t = setInterval(check, 60_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  if (!status || status.connected) return null;
  const text = !status.reachable
    ? "WhatsApp service is not running — messages are paused."
    : status.state === "qr" || status.state === "logged_out"
      ? "WhatsApp is not linked — scan the QR code to start sending messages."
      : "WhatsApp is disconnected — messages are paused until it reconnects.";
  return (
    <Link href="/dashboard/messages" className="block bg-red-600 px-4 py-2 text-center text-sm font-medium text-white">
      ⚠️ {text} <span className="underline">Fix →</span>
    </Link>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data: user } = useApi<User>("/api/auth/me"); // redirects to /login if not logged in
  const pgName = usePgName();

  if (!user) return <Loading />;

  return (
    <div className="flex min-h-screen flex-col pb-20 lg:pb-0">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link href="/dashboard" className="font-bold text-rose-700">
            {pgName}
          </Link>
          <nav className="hidden gap-1 lg:flex">
            {[...NAV.slice(0, -1), ...MORE].map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                  isActive(pathname, n.href) && n.href !== "/dashboard/more" ? "bg-rose-50 text-rose-700" : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                {n.label}
              </Link>
            ))}
          </nav>
          <span className="hidden text-xs text-slate-500 md:block">{user.name}</span>
        </div>
      </header>
      <WhatsAppBanner />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-5">{children}</main>

      {/* Bottom tab bar on phones */}
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-6 border-t border-slate-200 bg-white lg:hidden">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={`flex flex-col items-center py-2 text-xs ${isActive(pathname, n.href) ? "font-semibold text-rose-700" : "text-slate-500"}`}
          >
            <span className="text-lg leading-none">{n.icon}</span>
            {n.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
