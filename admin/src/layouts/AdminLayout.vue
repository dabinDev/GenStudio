<template>
  <div class="admin-layout">
    <div class="admin-ambient" aria-hidden="true">
      <span class="admin-ambient-drift admin-ambient-glow admin-ambient-glow-primary"></span>
      <span class="admin-ambient-drift admin-ambient-glow admin-ambient-glow-secondary"></span>
      <span class="admin-ambient-line admin-ambient-line-a"></span>
      <span class="admin-ambient-line admin-ambient-line-b"></span>
      <span class="admin-ambient-drift admin-ambient-dot admin-ambient-dot-a"></span>
      <span class="admin-ambient-drift admin-ambient-dot admin-ambient-dot-b"></span>
    </div>
    <aside class="admin-sidebar">
      <div class="admin-brand">
        <strong>创意工坊</strong>
        <span>管理后台</span>
      </div>
      <el-menu :default-active="activePath" router class="admin-menu">
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <span class="admin-menu-mark"><el-icon><component :is="iconFor(item.path)" /></el-icon></span>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <section class="admin-main">
      <header class="admin-topbar">
        <div>
          <p class="admin-topbar-label">后台控制台</p>
          <h1>{{ route.meta.title || '仪表盘' }}</h1>
        </div>
        <div class="admin-actions">
          <el-button circle :title="theme.isDark ? '切换到白天模式' : '切换到夜间模式'" @click="theme.toggle">
            <el-icon><component :is="theme.isDark ? Sunny : Moon" /></el-icon>
          </el-button>
          <div class="admin-user">
            <span>{{ displayName }}</span>
            <small>{{ auth.role || '管理员' }}</small>
          </div>
          <el-button type="primary" plain @click="handleLogout">退出</el-button>
        </div>
      </header>
      <nav class="admin-mobile-nav" aria-label="后台移动导航">
        <div ref="mobileNavTrackRef" class="admin-mobile-nav__track">
          <RouterLink
            v-for="item in menuItems"
            :key="item.path"
            :class="['admin-mobile-nav__item', activePath === item.path ? 'is-active' : '']"
            :to="item.path"
            :aria-current="activePath === item.path ? 'page' : undefined"
          >
            <el-icon><component :is="iconFor(item.path)" /></el-icon>
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>
      <main class="admin-content">
        <router-view />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  Cpu,
  Moon,
  Notebook,
  Odometer,
  Setting,
  Sunny,
  Tickets,
  User,
  MagicStick,
} from '@element-plus/icons-vue';
import { gsap } from 'gsap';
import { computed, nextTick, onMounted, onUnmounted, ref, watch, type Component } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import { visibleAdminMenuItems } from '@/adminNavigation';
import { useAdminAuthStore } from '@/stores/auth';
import { useAdminThemeStore } from '@/stores/theme';

const route = useRoute();
const auth = useAdminAuthStore();
const theme = useAdminThemeStore();

const MENU_ICONS: Record<string, Component> = {
  '/dashboard': Odometer,
  '/models': Cpu,
  '/prompts': MagicStick,
  '/users': User,
  '/records': Tickets,
  '/audit': Notebook,
  '/settings': Setting,
};

function iconFor(path: string): Component {
  return MENU_ICONS[path] ?? Setting;
}

const menuItems = computed(() => visibleAdminMenuItems((permission) => auth.can(permission)));
const activePath = computed(() => route.path);
const displayName = computed(() =>
  safeIdentityLabel(auth.user?.displayName || auth.user?.nickname, auth.user?.email || '管理员'),
);
const mobileNavTrackRef = ref<HTMLElement | null>(null);

let adminAmbientAnimations: gsap.core.Animation[] = [];

function teardownAdminAmbientAnimation() {
  adminAmbientAnimations.forEach((animation) => animation.kill());
  adminAmbientAnimations = [];
}

function setupAdminAmbientAnimation() {
  void nextTick(() => {
    teardownAdminAmbientAnimation();
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const driftNodes = Array.from(document.querySelectorAll<HTMLElement>('.admin-ambient-drift'));
    const lines = Array.from(document.querySelectorAll<HTMLElement>('.admin-ambient-line'));

    driftNodes.forEach((node, index) => {
      adminAmbientAnimations.push(
        gsap.to(node, {
          x: index % 2 === 0 ? 18 : -20,
          y: index % 2 === 0 ? -14 : 16,
          scale: 1.04,
          duration: 12 + index * 2,
          ease: 'sine.inOut',
          repeat: -1,
          yoyo: true,
        }),
      );
    });

    lines.forEach((line, index) => {
      adminAmbientAnimations.push(
        gsap.fromTo(
          line,
          { xPercent: index % 2 === 0 ? -14 : 14, autoAlpha: 0.18 },
          {
            xPercent: index % 2 === 0 ? 16 : -16,
            autoAlpha: 0.52,
            duration: 7 + index * 1.5,
            ease: 'sine.inOut',
            repeat: -1,
            yoyo: true,
          },
        ),
      );
    });
  });
}

function scrollActiveMobileNavIntoView() {
  const alignActiveMobileNav = () => {
    const track = mobileNavTrackRef.value;
    if (!track || track.clientWidth <= 0) return;

    const activeItem = track.querySelector<HTMLElement>('.admin-mobile-nav__item.is-active');
    if (!activeItem) return;
    const targetLeft = Math.max(
      0,
      activeItem.offsetLeft + activeItem.offsetWidth / 2 - track.clientWidth / 2,
    );
    track.scrollLeft = targetLeft;
    track.scrollTo({
      left: targetLeft,
      behavior: 'smooth',
    });
  };

  void nextTick(() => {
    alignActiveMobileNav();
    requestAnimationFrame(alignActiveMobileNav);
    window.setTimeout(alignActiveMobileNav, 180);
  });
}

function safeIdentityLabel(value: string | null | undefined, fallback: string) {
  const normalized = (value || '').trim();
  if (!normalized) return fallback;
  if (/[�]/.test(normalized) || /\?{2,}/.test(normalized)) return fallback;
  return normalized;
}

onMounted(() => {
  theme.init();
  setupAdminAmbientAnimation();
  scrollActiveMobileNavIntoView();
});

onUnmounted(() => {
  teardownAdminAmbientAnimation();
});

watch(() => theme.theme, () => setupAdminAmbientAnimation());
watch(activePath, () => scrollActiveMobileNavIntoView(), { flush: 'post' });
watch(() => menuItems.value.length, () => scrollActiveMobileNavIntoView(), { flush: 'post' });

async function handleLogout() {
  await auth.logout();
  window.location.href = '/#/auth?redirect=%2Fadmin%2F';
}
</script>
