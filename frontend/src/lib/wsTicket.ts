// FE-06 — single-use ticket for the WebSocket handshake.
//
// A browser cannot attach an Authorization header to a WebSocket handshake,
// so the socket used to carry the access token in its query string. That put a
// long-lived credential into access/proxy logs, browser history and any
// URL-capturing tooling. The client now trades the access token for a
// short-lived ticket over authenticated HTTP and puts only the ticket in the
// handshake URL. The backend stores it (hashed) in Redis for 60s and redeems it
// exactly once — see `core/security/tokens.py::create_ws_ticket`.

import { apiPost } from "@/lib/api";

/** Mirrors `core.security.tokens.WS_TICKET_TTL_SECONDS`. */
export const WS_TICKET_TTL_SECONDS = 60;

interface WsTicketEnvelope {
  success: boolean;
  data?: { ticket?: string; expires_in?: number };
}

/**
 * Request a fresh handshake ticket. Returns `null` when the backend cannot
 * mint one (e.g. its ticket store is unavailable) — callers must treat that as
 * "cannot connect", never as "connect unauthenticated".
 */
export async function fetchWsTicket(): Promise<string | null> {
  const res = await apiPost<WsTicketEnvelope>("/auth/ws-ticket");
  const ticket = res?.data?.ticket;
  return typeof ticket === "string" && ticket.length > 0 ? ticket : null;
}
