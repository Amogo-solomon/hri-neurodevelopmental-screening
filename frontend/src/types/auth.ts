export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: 'researcher' | 'clinician' | 'admin';
  is_active: boolean;
  is_verified: boolean;
  institution: string | null;
  created_at: string;
  last_login_at: string | null;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  full_name: string;
  password: string;
  institution?: string;
  role?: 'researcher' | 'clinician';
}

export interface PasswordChangeData {
  current_password: string;
  new_password: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}
