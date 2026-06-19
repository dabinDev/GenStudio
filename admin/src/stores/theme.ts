import { defineStore } from 'pinia';

type AdminTheme = 'light' | 'dark';

const SHARED_STORAGE_KEY = 'genstudio-theme';
const LEGACY_STORAGE_KEY = 'genstudio-admin-theme';

function normalizeTheme(value: string | null): AdminTheme | null {
  if (value === 'dark' || value === 'light') {
    return value;
  }
  return null;
}

export function readAdminThemeQuery(search: string): AdminTheme | null {
  return normalizeTheme(new URLSearchParams(search).get('theme'));
}

function readStoredTheme(): AdminTheme {
  if (typeof window !== 'undefined') {
    const queryTheme = readAdminThemeQuery(window.location.search);
    if (queryTheme) return queryTheme;
  }
  if (typeof localStorage === 'undefined') {
    return 'light';
  }
  return normalizeTheme(localStorage.getItem(SHARED_STORAGE_KEY))
    ?? normalizeTheme(localStorage.getItem(LEGACY_STORAGE_KEY))
    ?? 'light';
}

function applyTheme(theme: AdminTheme): void {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme;
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(SHARED_STORAGE_KEY, theme);
    localStorage.setItem(LEGACY_STORAGE_KEY, theme);
  }
}

export const useAdminThemeStore = defineStore('admin-theme', {
  state: () => ({
    theme: readStoredTheme(),
  }),
  getters: {
    isDark: (state) => state.theme === 'dark',
  },
  actions: {
    init() {
      applyTheme(this.theme);
    },
    toggle() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark';
      applyTheme(this.theme);
    },
  },
});
