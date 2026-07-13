<template>
  <section class="admin-page admin-forbidden">
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <p v-if="requiredPermission" class="admin-forbidden__hint">
      所需权限：<code>{{ requiredPermission }}</code>，请联系管理员为你的账号开通后再访问。
    </p>
    <div class="admin-forbidden__actions">
      <el-button v-if="isSystemError" type="primary" @click="retry">重试</el-button>
      <el-button @click="goBack">返回上一页</el-button>
      <el-button type="primary" :plain="isSystemError" @click="goDashboard">返回仪表盘</el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const isSystemError = computed(() => route.query.reason === 'system');
const requiredPermission = computed(() =>
  typeof route.query.permission === 'string' ? route.query.permission : '',
);
const title = computed(() => (isSystemError.value ? '后台服务异常' : '无权访问'));
const message = computed(() => (
  isSystemError.value
    ? '后台服务暂时不可用，请稍后重试。'
    : '当前账号没有访问该后台页面的权限。'
));

function retry() {
  window.location.reload();
}

function goBack() {
  if (window.history.length > 1) {
    router.back();
  } else {
    void router.push('/dashboard');
  }
}

function goDashboard() {
  void router.push('/dashboard');
}
</script>
