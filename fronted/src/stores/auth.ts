import { reactive } from "vue";

import { devLogin, fetchCurrentUser } from "../api";
import type { UserProfile } from "../types";

const state = reactive({
  loading: false,
  user: null as UserProfile | null,
  error: "",
});

export function useAuthStore() {
  async function loadCurrentUser() {
    state.loading = true;
    state.error = "";
    try {
      state.user = await fetchCurrentUser();
    } catch (error) {
      state.error = error instanceof Error ? error.message : "读取登录状态失败。";
    } finally {
      state.loading = false;
    }
  }

  async function loginForDevelopment() {
    state.loading = true;
    state.error = "";
    try {
      state.user = await devLogin();
    } catch (error) {
      state.error = error instanceof Error ? error.message : "开发登录失败。";
    } finally {
      state.loading = false;
    }
  }

  return {
    state,
    loadCurrentUser,
    loginForDevelopment,
  };
}
