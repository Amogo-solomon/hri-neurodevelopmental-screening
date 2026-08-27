'use client';
import { create } from 'zustand';
import type { AuthUser } from '@/types/auth';
import { tokenStorage } from '@/lib/api';

interface AuthStore {
  user:            AuthUser | null;
  isAuthenticated: boolean;
  isLoading:       boolean;
  setUser:         (user: AuthUser | null) => void;
  setLoading:      (v: boolean) => void;
  logout:          () => void;
  hydrate:         () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user:            null,
  isAuthenticated: false,
  isLoading:       true,

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setLoading: (v) => set({ isLoading: v }),

  logout: () => {
    tokenStorage.clear();
    set({ user: null, isAuthenticated: false });
  },

  hydrate: () => {
    const user   = tokenStorage.getUser();
    const access = tokenStorage.getAccess();
    set({
      user:            user && access ? user : null,
      isAuthenticated: !!(user && access),
      isLoading:       false,
    });
  },
}));
