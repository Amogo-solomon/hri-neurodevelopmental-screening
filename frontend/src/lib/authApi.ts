/**
 * authApi.ts — re-exports from the unified api.ts
 * Kept for backwards compatibility with existing imports.
 */
export {
  api as authApi,
  tokenStorage,
  apiLogin,
  apiRegister,
  apiLogout,
  apiGetMe,
  apiChangePassword,
  apiRequestPasswordReset,
  apiConfirmPasswordReset,
  apiAdminListUsers,
  apiAdminUpdateUser,
  apiAdminDeleteUser,
  apiAdminCreateUser,
  apiAuditLog,
} from './api';
