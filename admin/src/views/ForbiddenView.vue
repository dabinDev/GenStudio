<template>
  <section class="admin-page admin-forbidden">
    <h2>{{ title }}</h2>
    <p>{{ message }}</p>
    <el-button type="primary" @click="$router.push('/dashboard')">返回仪表盘</el-button>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();
const isSystemError = computed(() => route.query.reason === 'system');
const title = computed(() => (isSystemError.value ? '后台服务异常' : '无权访问'));
const message = computed(() => (
  isSystemError.value
    ? '后台服务暂时不可用，请稍后重试。'
    : '当前账号没有访问该后台页面的权限。'
));
</script>
