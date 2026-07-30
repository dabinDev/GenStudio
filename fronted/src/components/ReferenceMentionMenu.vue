<script setup lang="ts">
import { computed } from "vue";

import type { UploadedAsset } from "../types";

const props = defineProps<{
  assets: UploadedAsset[];
  query: string;
  activeIndex: number;
}>();

const emit = defineEmits<{
  select: [index: number];
  close: [];
}>();

const visibleAssets = computed(() => {
  const query = props.query.trim().toLowerCase();
  return props.assets
    .map((asset, index) => ({ asset, index: index + 1 }))
    .filter(({ asset, index }) => {
      if (!query) return true;
      return String(index).startsWith(query) || asset.fileName.toLowerCase().includes(query);
    });
});
</script>

<template>
  <div
    class="reference-mention-menu"
    role="listbox"
    aria-label="引用图片"
    @keydown.esc.stop="emit('close')"
  >
    <button
      v-for="(item, visibleIndex) in visibleAssets"
      :key="item.asset.id"
      type="button"
      class="reference-mention-option"
      role="option"
      :aria-label="`引用图片 ${item.index}`"
      :aria-selected="visibleIndex === activeIndex"
      @click="emit('select', item.index)"
    >
      <span class="reference-mention-number">@{{ item.index }}</span>
      <img
        :src="item.asset.thumbnailUrl || item.asset.localPreviewUrl || item.asset.publicUrl"
        :alt="item.asset.fileName"
      />
      <span class="reference-mention-file">{{ item.asset.fileName }}</span>
    </button>
  </div>
</template>
