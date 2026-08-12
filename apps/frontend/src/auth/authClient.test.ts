import { describe, expect, it } from "vitest";

import { createApiClient } from "../transport/apiClient";
import { createAuthClient } from "./authClient";

describe("authClient", () => {
  it("直接使用共享 Auth payload 调用四个 endpoint", async () => {
    const requests: Array<{ url: string; method: string; body: string | null }> = [];
    const apiClient = createApiClient({
      getAccessToken: () => "bearer-token",
      fetcher: async (input, init) => {
        requests.push({
          url: String(input),
          method: init?.method ?? "GET",
          body: typeof init?.body === "string" ? init.body : null,
        });
        const url = String(input);
        const data = url.endsWith("/login")
          ? {
              user: { id: "user-1", email: "user@example.com", createdAt: "2026-08-08T00:00:00Z" },
              token: "raw-token",
            }
          : url.endsWith("/logout")
            ? { revoked: true }
            : { id: "user-1", email: "user@example.com", createdAt: "2026-08-08T00:00:00Z" };
        return new Response(JSON.stringify({ ok: true, data, meta: { requestId: "req-auth" } }), {
          status: url.endsWith("/register") ? 201 : 200,
          headers: { "Content-Type": "application/json" },
        });
      },
    });
    const client = createAuthClient(apiClient);

    await client.register({ email: "user@example.com", password: "password-123" });
    const login = await client.login({ email: "user@example.com", password: "password-123" });
    const me = await client.me();
    const logout = await client.logout();

    expect(login.data.token).toBe("raw-token");
    expect(me.data.email).toBe("user@example.com");
    expect(logout.data).toEqual({ revoked: true });
    expect(requests).toEqual([
      {
        url: "/auth/register",
        method: "POST",
        body: JSON.stringify({ email: "user@example.com", password: "password-123" }),
      },
      {
        url: "/auth/login",
        method: "POST",
        body: JSON.stringify({ email: "user@example.com", password: "password-123" }),
      },
      { url: "/auth/me", method: "GET", body: null },
      { url: "/auth/logout", method: "POST", body: null },
    ]);
  });
});
