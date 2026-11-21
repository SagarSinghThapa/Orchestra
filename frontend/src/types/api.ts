export type UserRole = "admin" | "member" | "viewer";

export interface UserResponse {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email?: string;
  username?: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ApiErrorDetail {
  status: number;
  message: string;
  details?: unknown;
}
