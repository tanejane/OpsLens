import { ApiRequestError } from "./api-client";

export type SessionSnapshot = { id: string; revision: number; history: { turn: number; canonical_result: Record<string, unknown> }[]; evicted_turns: number };
type Transport = <T>(url: string, init?: RequestInit) => Promise<T>;
const KEY = "opslens.investigation.session.v1";

/** View-independent session transport. Browser storage contains no owner credential or evidence. */
export class InvestigationSessionClient {
  session?: SessionSnapshot;
  private storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  private needsReset = false;
  constructor(private request: Transport) {}
  private accept(session: SessionSnapshot) {
    this.session = session;
    this.storage?.setItem(KEY, session.id);
  }
  async restore(storage: Pick<Storage, "getItem" | "setItem" | "removeItem">) {
    this.storage = storage;
    const id = storage.getItem(KEY);
    if (!id) return;
    try {
      const body = await this.request<{ session: SessionSnapshot }>(`/api/investigation-sessions/${encodeURIComponent(id)}`);
      this.accept(body.session);
      return body.session.history.at(-1)?.canonical_result;
    } catch (error) {
      this.needsReset = true;
      if (error instanceof ApiRequestError && error.status === 404) storage.removeItem(KEY);
      throw error;
    }
  }
  async turn(question: string) {
    if (this.needsReset) throw new Error("Session unavailable. Choose New investigation before continuing.");
    if (!this.session) {
      const body = await this.request<{ session: SessionSnapshot }>("/api/investigation-sessions", { method: "POST" });
      this.accept(body.session);
    }
    try {
      const body = await this.request<{ session: SessionSnapshot; canonical_result: Record<string, unknown> }>("/api/investigations", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: this.session!.id, revision: this.session!.revision }),
      });
      this.accept(body.session);
      return body.canonical_result;
    } catch (error) {
      if (error instanceof ApiRequestError) {
        if (error.session) this.accept(error.session as SessionSnapshot);
        else if (error.status === 404) { this.session = undefined; this.needsReset = true; this.storage?.removeItem(KEY); }
        else if (error.status === 409) {
          // Refresh metadata only; never automatically replay Gemini or tools.
          let refreshed: SessionSnapshot | undefined;
          try { refreshed = (await this.request<{ session: SessionSnapshot }>(`/api/investigation-sessions/${this.session!.id}`)).session; this.accept(refreshed); } catch { /* Keep the conflict visible. */ }
          if (refreshed) throw new ApiRequestError(error.message, refreshed.history.at(-1)?.canonical_result, refreshed, 409);
        }
      }
      throw error;
    }
  }
  async reset() {
    if (this.session) {
      try { await this.request(`/api/investigation-sessions/${this.session.id}`, { method: "DELETE" }); }
      catch (error) { if (!(error instanceof ApiRequestError && error.status === 404)) throw error; }
    }
    this.session = undefined;
    this.needsReset = false;
    this.storage?.removeItem(KEY);
  }
}
