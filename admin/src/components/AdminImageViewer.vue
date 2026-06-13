<template>
  <Teleport to="body">
    <section
      v-if="visible && activeImage"
      class="admin-image-viewer"
      role="dialog"
      aria-modal="true"
      aria-label="图片浏览器"
      @click.self="closeViewer"
    >
      <div class="admin-image-viewer__toolbar">
        <div class="admin-image-viewer__title">
          <strong>{{ title || '图片预览' }}</strong>
          <span>{{ activeIndex + 1 }} / {{ images.length }} · {{ Math.round(scale * 100) }}%</span>
        </div>
        <div class="admin-image-viewer__actions">
          <button type="button" :disabled="!hasMultipleImages" title="上一张" @click="showPreviousImage">
            ←
          </button>
          <button type="button" :disabled="!hasMultipleImages" title="下一张" @click="showNextImage">
            →
          </button>
          <button type="button" title="缩小" @click="zoomImage(-0.18)">-</button>
          <button type="button" title="放大" @click="zoomImage(0.18)">+</button>
          <button type="button" title="重置" @click="resetTransform">1:1</button>
          <a :href="activeImage.url" :download="downloadFileName" title="保存图片" @click.stop>
            保存
          </a>
          <a :href="activeImage.url" target="_blank" rel="noreferrer" title="打开原图" @click.stop>原图</a>
          <button class="admin-image-viewer__close" type="button" title="关闭" @click="closeViewer">
            ×
          </button>
        </div>
      </div>

      <button
        v-if="hasMultipleImages"
        class="admin-image-viewer__nav admin-image-viewer__nav--prev"
        type="button"
        aria-label="上一张图片"
        @click="showPreviousImage"
      >
        ←
      </button>

      <div
        class="admin-image-viewer__stage"
        @wheel.prevent="handleWheel"
        @pointerdown="handlePointerDown"
        @pointermove="handlePointerMove"
        @pointerup="handlePointerUp"
        @pointercancel="handlePointerUp"
        @dblclick="resetTransform"
      >
        <img
          :key="activeImage.url"
          :src="activeImage.url"
          :alt="title || '图片预览'"
          :style="{ transform: viewerTransform }"
          draggable="false"
        />
      </div>

      <button
        v-if="hasMultipleImages"
        class="admin-image-viewer__nav admin-image-viewer__nav--next"
        type="button"
        aria-label="下一张图片"
        @click="showNextImage"
      >
        →
      </button>
    </section>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';

interface ViewerImage {
  url: string;
  thumbnailUrl?: string;
}

const props = defineProps<{
  visible: boolean;
  images: ViewerImage[];
  initialIndex?: number;
  title?: string;
}>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
}>();

const activeIndex = ref(0);
const scale = ref(1);
const offsetX = ref(0);
const offsetY = ref(0);
const dragging = ref(false);
const dragStartX = ref(0);
const dragStartY = ref(0);
const dragOriginX = ref(0);
const dragOriginY = ref(0);

const activeImage = computed(() => props.images[activeIndex.value] || null);
const hasMultipleImages = computed(() => props.images.length > 1);
const viewerTransform = computed(() => `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`);
const downloadFileName = computed(() => {
  const source = activeImage.value?.url || '';
  const fallback = `admin-image-${activeIndex.value + 1}.png`;
  const clean = source.split('?')[0].split('/').pop();
  return clean || fallback;
});

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function resetTransform() {
  scale.value = 1;
  offsetX.value = 0;
  offsetY.value = 0;
  dragging.value = false;
}

function setActiveIndex(index: number) {
  if (!props.images.length) {
    activeIndex.value = 0;
    return;
  }
  activeIndex.value = (index + props.images.length) % props.images.length;
  resetTransform();
}

function showPreviousImage() {
  if (!hasMultipleImages.value) return;
  setActiveIndex(activeIndex.value - 1);
}

function showNextImage() {
  if (!hasMultipleImages.value) return;
  setActiveIndex(activeIndex.value + 1);
}

function zoomImage(delta: number) {
  const nextScale = clamp(Number((scale.value + delta).toFixed(2)), 0.35, 4);
  scale.value = nextScale;
  if (nextScale <= 1) {
    offsetX.value = 0;
    offsetY.value = 0;
  }
}

function handleWheel(event: WheelEvent) {
  zoomImage(event.deltaY > 0 ? -0.16 : 0.16);
}

function handlePointerDown(event: PointerEvent) {
  dragging.value = true;
  dragStartX.value = event.clientX;
  dragStartY.value = event.clientY;
  dragOriginX.value = offsetX.value;
  dragOriginY.value = offsetY.value;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function handlePointerMove(event: PointerEvent) {
  if (!dragging.value) return;
  const deltaX = event.clientX - dragStartX.value;
  const deltaY = event.clientY - dragStartY.value;
  if (scale.value <= 1) return;
  offsetX.value = dragOriginX.value + deltaX;
  offsetY.value = dragOriginY.value + deltaY;
}

function handlePointerUp(event: PointerEvent) {
  if (event.currentTarget instanceof HTMLElement) {
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // Pointer capture may already be released.
    }
  }
  if (!dragging.value) return;
  const deltaX = event.clientX - dragStartX.value;
  const deltaY = event.clientY - dragStartY.value;
  dragging.value = false;
  if (scale.value <= 1 && Math.abs(deltaX) > 72 && Math.abs(deltaX) > Math.abs(deltaY) * 1.35) {
    if (deltaX > 0) {
      showPreviousImage();
    } else {
      showNextImage();
    }
  }
}

function closeViewer() {
  emit('update:visible', false);
}

function handleKeydown(event: KeyboardEvent) {
  if (!props.visible) return;
  if (event.key === 'Escape') closeViewer();
  if (event.key === 'ArrowLeft') showPreviousImage();
  if (event.key === 'ArrowRight') showNextImage();
  if (event.key === '+' || event.key === '=') zoomImage(0.18);
  if (event.key === '-' || event.key === '_') zoomImage(-0.18);
  if (event.key === '0') resetTransform();
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      setActiveIndex(props.initialIndex || 0);
      document.documentElement.classList.add('admin-image-viewer-open');
    } else {
      resetTransform();
      document.documentElement.classList.remove('admin-image-viewer-open');
    }
  },
  { immediate: true },
);

watch(
  () => props.initialIndex,
  (index) => {
    if (props.visible) {
      setActiveIndex(index || 0);
    }
  },
);

watch(
  () => props.images.length,
  () => {
    if (activeIndex.value >= props.images.length) {
      setActiveIndex(0);
    }
  },
);

window.addEventListener('keydown', handleKeydown);

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown);
  document.documentElement.classList.remove('admin-image-viewer-open');
});

defineExpose({
  showPreviousImage,
  showNextImage,
  downloadActiveImage: downloadFileName,
});
</script>
