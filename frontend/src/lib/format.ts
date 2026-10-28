/** ₹ with Indian digit grouping: 150000 -> ₹1,50,000 */
export function inr(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return "—";
  return (amount < 0 ? "-₹" : "₹") + Math.abs(amount).toLocaleString("en-IN");
}

const SHARING: Record<number, string> = { 1: "Single", 2: "Double", 3: "Triple" };
export const sharingLabel = (n: number) => SHARING[n] ?? `${n}-sharing`;

export const STATUS_LABEL: Record<string, string> = {
  active: "Active",
  on_notice: "On notice",
  vacated: "Vacated",
  paid: "Paid",
  partial: "Partial",
  unpaid: "Unpaid",
};

/** "2026-11-05" -> "05 Nov 2026" */
export function fdate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function fdatetime(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  });
}

/** "2026-11-01" -> "Nov 2026" */
export function monthLabel(value: string): string {
  const [y, m] = value.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "short", year: "numeric" });
}

/** Today's date in IST as YYYY-MM-DD */
export function todayIST(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

/** "2026-11-05" -> "2026-11" */
export const monthKey = (ymd: string) => ymd.slice(0, 7);

export function shiftMonth(key: string, delta: number): string {
  const [y, m] = key.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function daysInMonth(ymd: string): number {
  const [y, m] = ymd.split("-").map(Number);
  return new Date(y, m, 0).getDate();
}

/** "919876543210" -> "98765 43210" */
export function phone(value: string | null | undefined): string {
  if (!value) return "—";
  const local = value.length === 12 && value.startsWith("91") ? value.slice(2) : value;
  return local.length === 10 ? `${local.slice(0, 5)} ${local.slice(5)}` : local;
}
