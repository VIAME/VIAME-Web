<script lang="ts">
import { defineComponent } from '@vue/composition-api';

export default defineComponent({
  props: {
    width: {
      type: Number,
      default: 300,
    },
  },
});
</script>

<template>
  <v-card
    :width="width"
    tile
    class="sidebar d-flex flex-column overflow-hidden"
    style="z-index:1;"
  >
    <slot />
  </v-card>
</template>

<style lang="scss">
.sidebar {
  max-height: calc(100vh - 112px);
}

.settings-header {
  opacity: 0.7;
  font-size: 14px;
}
</style>
