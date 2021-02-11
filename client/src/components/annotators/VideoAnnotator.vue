<script lang="ts">
import { defineComponent, PropType } from '@vue/composition-api';
import { Flick } from './mediaControllerType';
import useMediaController from './useMediaController';

export default defineComponent({
  name: 'VideoAnnotator',

  props: {
    videoUrl: {
      type: String,
      required: true,
    },
    videoPlayerAttributes: {
      type: Object as PropType<{ [key: string]: string }>,
      default: () => ({}),
    },
    frameRate: {
      type: Number,
      required: true,
    },
  },

  setup(props) {
    const commonMedia = useMediaController({ hasFlicks: true });
    const { data } = commonMedia;

    function makeVideo() {
      const video = document.createElement('video');
      video.preload = 'auto';
      video.src = props.videoUrl;
      Object.assign(video, props.videoPlayerAttributes);
      return video;
    }
    const video = makeVideo();

    function syncWithVideo() {
      if (data.playing) {
        const newFrame = Math.round(video.currentTime * props.frameRate);
        if (newFrame !== data.frame) {
          data.frame = newFrame;
          data.syncedFrame = newFrame;
        }
        data.flick = Math.round(video.currentTime * Flick);
        commonMedia.geoViewerRef.value.scheduleAnimationFrame(syncWithVideo);
      }
    }

    async function play() {
      try {
        await video.play();
        data.playing = true;
        syncWithVideo();
      } catch (ex) {
        console.error(ex);
      }
    }

    /**
     * VideoAnnotator emits frame changes immediately rather than
     * waiting for video buffering to catch up.
     */
    async function seek(frame: number) {
      video.currentTime = frame / props.frameRate;
      // forge inaccurate flick from requested seek time.
      // it will be corrected when the seeked event is fired.
      data.flick = Math.round((frame / props.frameRate) * Flick);
      data.frame = Math.round(video.currentTime * props.frameRate);
    }

    function pause() {
      video.pause();
      data.playing = false;
    }

    const {
      cursorHandler,
      initializeViewer,
      mediaController,
    } = commonMedia.initialize({ seek, play, pause });

    /**
     * Initialize the Quad feature layer once
     * video metadata has been fetched.
     */
    function loadedMetadata() {
      video.removeEventListener('loadedmetadata', loadedMetadata);
      const width = video.videoWidth;
      const height = video.videoHeight;
      data.maxFrame = props.frameRate * video.duration;
      initializeViewer(width, height);
      const quadFeatureLayer = commonMedia.geoViewerRef.value.createLayer('feature', {
        features: ['quad.video'],
      });
      quadFeatureLayer
        .createFeature('quad')
        .data([
          {
            ul: { x: 0, y: 0 },
            lr: { x: width, y: height },
            video,
          },
        ])
        .draw();
      // Force the first frame to load on slow networks.
      // See https://github.com/VIAME/VIAME-Web/issues/447 for more details.
      seek(0);
      data.ready = true;
    }

    function pendingUpdate() {
      const syncedFrame = Math.round(video.currentTime * props.frameRate);
      // Don't update syncedFrame until state settles.
      if (data.frame === syncedFrame) {
        data.syncedFrame = syncedFrame;
        data.flick = Math.round(video.currentTime * Flick);
      }
    }

    video.addEventListener('loadedmetadata', loadedMetadata);
    video.addEventListener('seeked', pendingUpdate);

    return {
      data,
      imageCursorRef: commonMedia.imageCursorRef,
      containerRef: commonMedia.containerRef,
      onResize: commonMedia.onResize,
      cursorHandler,
      mediaController,
    };
  },
});
</script>

<template>
  <div
    v-resize="onResize"
    class="video-annotator"
    :style="{ cursor: data.cursor }"
  >
    <div
      ref="imageCursorRef"
      class="imageCursor"
    >
      <v-icon> {{ data.imageCursor }} </v-icon>
    </div>
    <div
      ref="containerRef"
      class="playback-container"
      @mousemove="cursorHandler.handleMouseMove"
      @mouseleave="cursorHandler.handleMouseLeave"
      @mouseover="cursorHandler.handleMouseEnter"
    />
    <slot name="control" />
    <slot v-if="data.ready" />
  </div>
</template>

<style lang="scss" scoped>
@import "./annotator.scss";
</style>
