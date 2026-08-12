/** 对浏览器安全的认证用户 DTO。 */
export interface AuthUser {
  id: string;
  email: string;
  createdAt: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

/** raw token 只在登录成功边界返回。 */
export interface LoginData {
  user: AuthUser;
  token: string;
}

export interface LogoutData {
  revoked: true;
}
