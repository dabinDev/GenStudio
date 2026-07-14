import { reactive } from "vue";

import {
  changeMyPassword,
  devLogin,
  fetchCsrfToken,
  fetchCurrentUser,
  fetchMyCredits,
  loginWithPassword,
  logout,
  registerAccount,
  setCsrfToken,
  updateMyProfile,
} from "../api";
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
      if (state.user) {
        await fetchCsrfToken();
      } else {
        setCsrfToken("");
      }
    } catch (error) {
      state.error = error instanceof Error ? error.message : "读取登录状态失败。";
    } finally {
      state.loading = false;
    }
  }

  async function refreshCredits() {
    if (!state.user) return;
    const credits = await fetchMyCredits();
    state.user = {
      ...state.user,
      credits: credits.account,
    };
  }

  async function registerWithPassword(payload: { email?: string; phone?: string; password: string; nickname?: string }) {
    state.loading = true;
    state.error = "";
    try {
      state.user = await registerAccount(payload);
    } catch (error) {
      state.error = error instanceof Error ? error.message : "注册失败。";
      throw error;
    } finally {
      state.loading = false;
    }
  }

  async function login(payload: { identifier: string; password: string }) {
    state.loading = true;
    state.error = "";
    try {
      state.user = await loginWithPassword(payload);
    } catch (error) {
      state.error = error instanceof Error ? error.message : "登录失败。";
      throw error;
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
      throw error;
    } finally {
      state.loading = false;
    }
  }

  async function updateProfile(payload: { nickname?: string; phone?: string; avatarUrl?: string }) {
    state.loading = true;
    state.error = "";
    try {
      state.user = await updateMyProfile(payload);
    } catch (error) {
      state.error = error instanceof Error ? error.message : "保存个人信息失败。";
      throw error;
    } finally {
      state.loading = false;
    }
  }

  async function changePassword(payload: { currentPassword: string; newPassword: string }) {
    state.loading = true;
    state.error = "";
    try {
      await changeMyPassword(payload);
    } catch (error) {
      state.error = error instanceof Error ? error.message : "修改密码失败。";
      throw error;
    } finally {
      state.loading = false;
    }
  }

  async function logoutCurrentUser() {
    state.loading = true;
    state.error = "";
    try {
      await logout();
      state.user = null;
    } catch (error) {
      state.error = error instanceof Error ? error.message : "退出登录失败。";
      throw error;
    } finally {
      state.loading = false;
    }
  }

  return {
    state,
    loadCurrentUser,
    refreshCredits,
    registerWithPassword,
    login,
    loginForDevelopment,
    updateProfile,
    changePassword,
    logoutCurrentUser,
  };
}
