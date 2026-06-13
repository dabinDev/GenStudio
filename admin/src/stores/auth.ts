import { defineStore } from 'pinia';

import {
  fetchAdminPermissions,
  fetchCsrfToken,
  fetchCurrentUser,
  logoutAdmin,
} from '@/api/admin';
import { setAdminCsrfToken } from '@/api/http';
import type { AdminUserSession } from '@/types';

interface AdminAuthState {
  user: AdminUserSession | null;
  csrfToken: string;
  role: string;
  permissions: string[];
  bootstrapped: boolean;
}

export const useAdminAuthStore = defineStore('admin-auth', {
  state: (): AdminAuthState => ({
    user: null,
    csrfToken: '',
    role: '',
    permissions: [],
    bootstrapped: false,
  }),
  getters: {
    isAdmin: (state) => Boolean(state.user?.isAdmin),
  },
  actions: {
    async bootstrap() {
      if (this.bootstrapped) {
        return;
      }

      this.user = await fetchCurrentUser();
      if (!this.user) {
        this.bootstrapped = true;
        return;
      }

      this.csrfToken = await fetchCsrfToken();
      if (!this.user.isAdmin) {
        this.role = '';
        this.permissions = [];
        this.bootstrapped = true;
        return;
      }

      const permissions = await fetchAdminPermissions();
      this.role = permissions.role;
      this.permissions = permissions.permissions;
      this.bootstrapped = true;
    },
    can(permission: string) {
      return this.permissions.includes(permission);
    },
    async logout() {
      try {
        await logoutAdmin();
      } finally {
        this.user = null;
        this.csrfToken = '';
        this.role = '';
        this.permissions = [];
        this.bootstrapped = false;
        setAdminCsrfToken('');
      }
    },
  },
});
