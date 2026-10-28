// Shapes returned by the FastAPI backend (see backend/app/schemas.py)

export type TenantStatus = "active" | "on_notice" | "vacated";
export type RentStatus = "paid" | "partial" | "unpaid";
export type PaymentMode = "cash" | "upi" | "bank";

export type User = { id: number; name: string; email: string | null; role: string };

export type Payment = {
  id: number;
  rent_record_id: number;
  amount: number;
  paid_on: string;
  mode: PaymentMode;
  reference: string;
  note: string;
};

export type RentRecord = {
  id: number;
  tenant_id: number;
  month: string;
  amount_due: number;
  amount_paid: number;
  balance: number;
  status: RentStatus;
  note: string;
  payments: Payment[];
};

export type TenantDocument = {
  id: number;
  kind: "id_proof" | "photo" | "other";
  original_name: string;
  mime_type: string;
  size_bytes: number;
  uploaded_at: string;
};

export type Settlement = {
  move_out_date: string;
  deposit_collected: number;
  pending_dues: number;
  total_deductions: number;
  refund_amount: number;
  notes: string;
  settled_on: string;
  deductions: { reason: string; amount: number }[];
};

export type TenantSummary = {
  id: number;
  name: string;
  phone: string;
  room_id: number;
  room_number: string;
  category_name: string;
  sharing: number;
  rent: number | null;
  default_rent: number | null;
  rent_override: number | null;
  deposit_amount: number;
  deposit_collected: number;
  deposit_balance: number;
  joining_date: string;
  status: TenantStatus;
  notice_date: string | null;
  move_out_date: string | null;
  outstanding: number;
  current_month_status: RentStatus | null;
};

export type TenantDetail = TenantSummary & {
  biometric_no: string;
  office_address: string;
  permanent_address: string;
  notes: string;
  created_at: string;
  documents: TenantDocument[];
  rent_records: RentRecord[];
  settlement: Settlement | null;
};

export type Room = {
  id: number;
  number: string;
  floor: number;
  category_id: number;
  category_name: string;
  max_sharing: number;
  notes: string;
  is_active: boolean;
  occupants: { id: number; name: string; sharing: number; status: TenantStatus }[];
  capacity_now: number;
};

export type Category = {
  id: number;
  name: string;
  description: string;
  max_sharing: number;
  sort_order: number;
  rates: { sharing: number; monthly_rent: number | null }[];
  room_count: number;
};

export type MonthView = {
  month: string;
  expected: number;
  collected: number;
  pending: number;
  counts: Record<RentStatus, number>;
  rows: {
    record: RentRecord;
    tenant_name: string;
    tenant_status: TenantStatus;
    room_number: string;
    phone: string;
  }[];
};

export type UnpaidRow = {
  tenant_id: number;
  name: string;
  room: string;
  phone: string;
  month_status: RentStatus | null;
  month_balance: number;
  older_dues: number;
  deposit_balance: number;
  amount: number;
  label: string;
};

export type Audit = {
  id: number;
  actor_name: string;
  entity_type: string;
  entity_id: number | null;
  action: string;
  summary: string;
  created_at: string;
};

export type Dashboard = {
  today: string;
  month: string;
  rent: { expected: number; collected: number; pending: number } & Record<RentStatus, number>;
  unpaid: UnpaidRow[];
  tenants: Record<TenantStatus, number>;
  rooms: { occupied: number; empty: number; free_beds: number };
  deposit_pending: number;
  on_notice: { id: number; name: string; room: string; move_out_date: string | null }[];
  whatsapp: { reachable: boolean; connected: boolean; state: string };
  owner_whatsapp_set: boolean;
  site_ready: boolean;
  messages_7d: { sent: number; pending: number; failed: number };
  recent_activity: Audit[];
};

export type Message = {
  id: number;
  kind: "rent_reminder" | "owner_report" | "owner_change" | "system";
  recipient: string;
  body: string;
  status: "pending" | "sending" | "sent" | "failed" | "unknown" | "skipped" | "expired";
  attempts: number;
  error: string;
  tenant_id: number | null;
  created_at: string;
  sent_at: string | null;
};

export type WhatsAppStatus = {
  reachable: boolean;
  connected: boolean;
  state: string;
  qr: string | null;
  me: string | null;
  lastError?: string | null;
};

export type SiteContent = {
  pg_name: string;
  tagline: string;
  about: string;
  who_can_stay: string;
  address: string;
  maps_link: string;
  phone: string;
  whatsapp: string;
  food: string;
  amenities: string[];
  rules: string[];
  show_prices: boolean;
};

export type GalleryItem = {
  id: number;
  kind: "photo" | "video" | "video_url";
  url: string | null;
  caption: string;
  sort_order: number;
  media_url: string | null;
};

export type PublicSite = {
  content: SiteContent;
  prices: {
    name: string;
    description: string;
    max_sharing: number;
    rates: { sharing: number; monthly_rent: number }[];
  }[];
  gallery: GalleryItem[];
};
