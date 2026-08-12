import type {
  AuthUser,
  LoginData,
  LoginRequest,
  LogoutData,
  RegisterRequest,
} from "@super-ai/api-contracts";

import type { ApiClient, ApiResult } from "../transport/apiClient";

export interface AuthClient {
  register(payload: RegisterRequest): Promise<ApiResult<AuthUser>>;
  login(payload: LoginRequest): Promise<ApiResult<LoginData>>;
  logout(): Promise<ApiResult<LogoutData>>;
  me(): Promise<ApiResult<AuthUser>>;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export function createAuthClient(apiClient: ApiClient): AuthClient {
  return {
    register: (payload) => apiClient.request<AuthUser>("/auth/register", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
    login: (payload) => apiClient.request<LoginData>("/auth/login", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
    logout: () => apiClient.request<LogoutData>("/auth/logout", { method: "POST" }),
    me: () => apiClient.request<AuthUser>("/auth/me"),
  };
}
