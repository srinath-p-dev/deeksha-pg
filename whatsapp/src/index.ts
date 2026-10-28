/**
 * Internal WhatsApp service (unofficial, via Baileys).
 *
 * Endpoints (all require the X-Internal-Token header):
 *   GET  /status   -> { connected, state, qr, me, lastError }
 *   POST /send     -> { phone: "91XXXXXXXXXX", text: "..." }
 *   POST /logout   -> unlink this number (a new QR appears)
 *
 * Node 22.18+ runs this TypeScript file directly (type stripping), no build step.
 * Pacing between messages is done by the backend worker; this service also
 * enforces a minimum gap and sends strictly one message at a time.
 */
import { timingSafeEqual } from "node:crypto";
import { rm } from "node:fs/promises";

import makeWASocket, {
  Browsers,
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
} from "baileys";
import type { WASocket } from "baileys";
import express from "express";
import type { NextFunction, Request, Response } from "express";
import pino from "pino";
import QRCode from "qrcode";

const PORT = Number(process.env.PORT ?? 3001);
const HOST = process.env.HOST ?? "127.0.0.1";
const TOKEN = process.env.WHATSAPP_TOKEN ?? "dev-whatsapp-token";
const SESSION_DIR = process.env.SESSION_DIR ?? "./session";
const MIN_GAP_MS = Number(process.env.MIN_GAP_MS ?? 5000);

const log = pino({ level: process.env.LOG_LEVEL ?? "info" });
const baileysLog = pino({ level: "warn" });

type State = "starting" | "qr" | "connecting" | "open" | "closed" | "logged_out";

let sock: WASocket | null = null;
let state: State = "starting";
let qrDataUrl: string | null = null;
let me: string | null = null;
let lastError: string | null = null;
let lastSentAt = 0;
let reconnectDelay = 2000;

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function connect(): Promise<void> {
  state = "connecting";
  const { state: auth, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
  const { version } = await fetchLatestBaileysVersion();

  const socket = makeWASocket({
    version,
    auth,
    logger: baileysLog,
    browser: Browsers.ubuntu("Chrome"),
    markOnlineOnConnect: false, // don't show "online" to everyone all day
    syncFullHistory: false,
  });
  sock = socket;

  socket.ev.on("creds.update", saveCreds);

  socket.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      state = "qr";
      qrDataUrl = await QRCode.toDataURL(qr, { margin: 1, width: 300 });
      log.info("New QR code available — scan it from the dashboard (Messages page)");
    }

    if (connection === "open") {
      state = "open";
      qrDataUrl = null;
      lastError = null;
      reconnectDelay = 2000;
      me = socket.user?.id?.split(":")[0]?.split("@")[0] ?? null;
      log.info({ me }, "WhatsApp connected");
    }

    if (connection === "close") {
      const code = (lastDisconnect?.error as { output?: { statusCode?: number } } | undefined)
        ?.output?.statusCode;
      lastError = lastDisconnect?.error?.message ?? `closed (${code})`;
      me = null;
      if (code === DisconnectReason.loggedOut) {
        // Unlinked from the phone: wipe the session and show a fresh QR
        state = "logged_out";
        log.warn("Logged out from WhatsApp; clearing session");
        await rm(SESSION_DIR, { recursive: true, force: true });
        setTimeout(start, 2000);
      } else {
        state = "closed";
        log.warn({ code, lastError, retryInMs: reconnectDelay }, "Connection closed; reconnecting");
        setTimeout(start, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 5 * 60_000);
      }
    }
  });
}

// ---------- HTTP API ----------

const app = express();
app.use(express.json({ limit: "64kb" }));

function requireToken(req: Request, res: Response, next: NextFunction) {
  const given = Buffer.from(req.header("x-internal-token") ?? "");
  const expected = Buffer.from(TOKEN);
  if (given.length !== expected.length || !timingSafeEqual(given, expected)) {
    res.status(401).json({ error: "unauthorized", retriable: false });
    return;
  }
  next();
}
app.use(requireToken);

app.get("/status", (_req, res) => {
  res.json({ connected: state === "open", state, qr: qrDataUrl, me, lastError });
});

// One send at a time, in order
let queue: Promise<unknown> = Promise.resolve();

async function sendOne(phone: string, text: string): Promise<{ status: number; body: object }> {
  if (!sock || state !== "open") {
    return { status: 503, body: { error: `WhatsApp not connected (${state})`, retriable: true } };
  }
  const wait = MIN_GAP_MS - (Date.now() - lastSentAt);
  if (wait > 0) await sleep(wait);

  const jid = `${phone}@s.whatsapp.net`;
  const [check] = (await sock.onWhatsApp(jid)) ?? [];
  if (!check?.exists) {
    log.warn({ phone }, "Number is not on WhatsApp");
    return { status: 400, body: { error: "This number is not on WhatsApp", retriable: false } };
  }
  const target = check.jid ?? jid;

  // Look human: show "typing…" briefly before sending
  await sock.sendPresenceUpdate("composing", target);
  await sleep(1000 + Math.random() * 2000);
  await sock.sendPresenceUpdate("paused", target);

  await sock.sendMessage(target, { text });
  lastSentAt = Date.now();
  log.info({ phone, chars: text.length }, "Message sent");
  return { status: 200, body: { ok: true } };
}

app.post("/send", async (req, res) => {
  const { phone, text } = req.body ?? {};
  if (typeof phone !== "string" || !/^\d{10,15}$/.test(phone)) {
    res.status(400).json({ error: "phone must be digits with country code", retriable: false });
    return;
  }
  if (typeof text !== "string" || !text.trim() || text.length > 4000) {
    res.status(400).json({ error: "text must be 1-4000 characters", retriable: false });
    return;
  }
  const job = queue.then(() => sendOne(phone, text));
  queue = job.catch(() => undefined);
  try {
    const result = await job;
    res.status(result.status).json(result.body);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    log.error({ phone, err: message }, "Send failed");
    res.status(502).json({ error: message, retriable: true });
  }
});

app.post("/logout", async (_req, res) => {
  try {
    await sock?.logout();
  } catch (err) {
    log.warn({ err }, "Logout call failed; clearing session anyway");
    await rm(SESSION_DIR, { recursive: true, force: true });
    setTimeout(start, 1000);
  }
  res.json({ ok: true });
});

function start(): void {
  connect().catch((err) => {
    lastError = String(err);
    state = "closed";
    log.error({ err }, "Connect failed; retrying in 30s");
    setTimeout(start, 30_000);
  });
}

app.listen(PORT, HOST, () => {
  log.info(`WhatsApp service listening on http://${HOST}:${PORT}`);
  start();
});
