<script lang="ts">
import { computed, defineComponent, PropType } from '@vue/composition-api';
import { injectMediaController } from '../annotators/useMediaController';

export default defineComponent({
  name: 'FileNameTimeDisplay',
  props: {
    displayType: {
      type: String as PropType<'filename' |'time'>,
      required: true,
    },
  },
  setup(props) {
    const {
      currentTime, duration, filename, frame, trueVideoFrame,
    } = injectMediaController();
    const display = computed(() => {
      if (props.displayType === 'filename') {
        return filename.value;
      } if (props.displayType === 'time') {
        return `${new Date(currentTime.value * 1000).toISOString().substr(11, 8)} / ${new Date(duration.value * 1000).toISOString().substr(11, 8)}`;
      }
      return 'unsupported display';
    });
    return {
      display,
      frame,
      trueVideoFrame,
      currentTime,
    };
  },
});
</script>

<template>
  <span>
    <span>
      {{ display }}
    </span>
    <span class="border-radius mr-1">frame {{ frame }}</span>
    <span class="border-radius mr-1">real {{ trueVideoFrame.toFixed(3) }}</span>
    <span class="border-radius">ts {{ currentTime.toFixed(6) }}</span>
  </span>
</template>
