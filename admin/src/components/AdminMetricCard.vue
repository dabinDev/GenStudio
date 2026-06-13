<template>
  <article class="admin-metric-card">
    <div>
      <p class="admin-metric-card__label">{{ label }}</p>
      <strong class="admin-metric-card__value">{{ value }}</strong>
    </div>
    <span v-if="tone" class="admin-metric-card__tone" :data-tone="tone">{{ toneText }}</span>
    <small v-if="hint" class="admin-metric-card__hint">{{ hint }}</small>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'good' | 'warn' | 'danger';
}>();

const toneText = computed(() => {
  if (props.tone === 'good') return '稳';
  if (props.tone === 'warn') return '警';
  return '险';
});
</script>
