<script lang="ts">
import {
  defineComponent, ref, onUnmounted, PropType,
} from '@vue/composition-api';
import useMediaController from './useMediaController';

export interface ImageDataItem {
  url: string;
  filename: string;
}

interface ImageDataItemInternal extends ImageDataItem {
  image: HTMLImageElement;
  cached: boolean; // true if onloadPromise has resolved
  frame: number; // frame number this image belongs to
  onloadPromise: Promise<boolean>;
}

function loadImageFunc(imageDataItem: ImageDataItem, img: HTMLImageElement) {
  // eslint-disable-next-line no-param-reassign
  img.src = imageDataItem.url;
}

export default defineComponent({
  name: 'ImageAnnotator',

  props: {
    imageData: {
      type: Array as PropType<ImageDataItem[]>,
      required: true,
    },
    frameRate: {
      type: Number,
      required: true,
    },
  },

  setup(props) {
    const loadingVideo = ref(false);
    const loadingImage = ref(true);
    const commonMedia = useMediaController();
    const { data } = commonMedia;
    data.flick = undefined;
    data.maxFrame = props.imageData.length - 1;

    // Below are configuration settings we can set until we decide on good numbers to utilize.
    const local = {
      playCache: 1, // seconds required to be fully cached before playback
      cacheSeconds: 6, // seconds to cache from the current frame
      frontBackRatio: 0.9, // 90% forward frames, 10% backward frames when caching
      imgs: new Array<ImageDataItemInternal | undefined>(props.imageData.length),
      pendingImgs: new Set<ImageDataItemInternal>(),
      lastFrame: -1,
      width: 0,
      height: 0,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      quadFeature: undefined as any,
    };

    function forceUnload(imgInternal: ImageDataItemInternal) {
      // Removal from list indicates we are no longer attempting to load this image
      local.imgs[imgInternal.frame] = undefined;
      // unset src to cancel outstanding load request
      // eslint-disable-next-line no-param-reassign
      imgInternal.image.src = '';
      local.pendingImgs.delete(imgInternal);
    }

    /**
     * When the component is unmounted, cancel all outstanding
     * requests for image load.
     */
    onUnmounted(() => Array.from(local.pendingImgs).forEach(forceUnload));

    /**
     * expectFrame when you know local.imgs[i] should not be undefined
     */
    function expectFrame(i: number) {
      const imgInternal = local.imgs[i];
      if (!imgInternal) {
        throw new Error(`imgs ${i} was undefined after assignment.`);
      }
      return imgInternal;
    }

    /**
     * Draw image to the GeoJS map, and update the map dimensions if they have changed.
     */
    function drawImage(img: HTMLImageElement) {
      if (
        img.naturalWidth > 0
        && img.naturalHeight > 0
        && ((img.naturalWidth !== local.width) || (img.naturalHeight !== local.height))
      ) {
        /**
         * Only update dimensions if the image has loaded
         * AND the dimensions have changed
         */
        local.width = img.naturalWidth;
        local.height = img.naturalHeight;
        commonMedia.resetMapDimensions(local.width, local.height);
      }
      local.quadFeature
        .data([
          {
            ul: { x: 0, y: 0 },
            lr: { x: local.width, y: local.height },
            image: img,
          },
        ])
        .draw();
    }

    /**
     * Adds a single frame to the pendingImgs array for loading and assigns it to the master
     * imgs list. Once the image is loaded it is removed from the pendingImgs
     * @param {int} i the image to cache if it isn't already assigned
     */
    function cacheFrame(i: number): ImageDataItemInternal {
      const { imgs, pendingImgs } = local;
      if (!imgs[i]) {
        const img = new Image();
        img.crossOrigin = 'Anonymous';
        const newImgInternal = {
          ...props.imageData[i],
          frame: i,
          image: img,
          cached: false,
          onloadPromise: new Promise<boolean>((resolve) => {
            img.onload = () => {
              const imgInternal = expectFrame(i);
              pendingImgs.delete(imgInternal);
              imgInternal.cached = true;
              resolve(true);
            };
            img.onerror = () => resolve(false);
          }),
        };
        imgs[i] = newImgInternal;
        pendingImgs.add(newImgInternal);
        loadImageFunc(newImgInternal, img);
      }
      return expectFrame(i);
    }

    /**
     * Caches a new range of frames to load in a forward->back pattern from the current frame
     * This allows for easily seeking backwards after seeking initially
     * @param {int} min lower bound frame number for caching
     * @param {int} max upper bound frame number for caching
     */
    function cacheNewRange(min: number, max: number) {
      for (let i = data.frame; i <= max; i += 1) {
        cacheFrame(i);
        const minusFrame = data.frame - (i - data.frame);
        if (minusFrame >= min) {
          cacheFrame(minusFrame);
        }
      }
    }

    /**
     * Begins loading a set of images around the current frame.  If the image is not playing
     * it will give priority tothe currently loaded frame
     */
    async function cacheImages() {
      const cachedFrames = local.cacheSeconds * props.frameRate;
      const min = Math.floor(Math.max(0, data.frame - cachedFrames * (1 - local.frontBackRatio)));
      const max = Math.ceil(
        Math.min(data.frame + local.frontBackRatio * cachedFrames, data.maxFrame),
      );
      const frameDiff = Math.abs(data.frame - local.lastFrame);
      const prevFrame = (data.frame < local.lastFrame);
      local.pendingImgs.forEach((imgInternal) => {
        // the current loading cache needs to be wiped out if we seek forward, backwards or
        // if we are out of the current range of the cache
        if (imgInternal.frame < min
          || imgInternal.frame > max
          || frameDiff > 1 || prevFrame
          || (!data.playing && frameDiff === 1)
        ) {
          forceUnload(imgInternal);
        }
      });
      let result = true;
      // if not playing we want the seeked to frame immediately and prevent caching until loaded
      if (!data.playing && !local.imgs[data.frame] && data.frame > 0) {
        result = await cacheFrame(data.frame)?.onloadPromise;
      }
      // Cache a new range of images based on current frame
      if (result) {
        cacheNewRange(min, max);
      }
    }

    async function seek(f: number) {
      let newFrame = f;
      if (f < 0) newFrame = 0;
      if (f > data.maxFrame) newFrame = data.maxFrame;
      local.lastFrame = data.frame;
      data.frame = newFrame;
      data.syncedFrame = newFrame;
      if (data.frame !== 0 && local.lastFrame === data.frame) {
        return;
      }

      cacheImages();
      const imgInternal = expectFrame(newFrame);
      drawImage(imgInternal.image);
      if (!imgInternal.cached) {
        loadingImage.value = true;
        // else wait for it to load
        await imgInternal.onloadPromise;
        if (imgInternal.frame === data.frame) {
          loadingImage.value = false;
          // if the seek hasn't changed since the image completed loading, draw it.
          drawImage(imgInternal.image);
        }
      } else {
        loadingImage.value = false;
      }
    }

    function pause() {
      data.playing = false;
      loadingVideo.value = false;
    }

    /**
     * Checks to see if there are enough cached images to play for X seconds.
     * @param frame start frame to look for.
     * @param seconds num seconds to look for cache
     * @returns Promise to await for caching.
     */
    function checkCached(frame: number, seconds: number) {
      const upper = Math.min(frame + (seconds * props.frameRate), data.maxFrame);
      return local.imgs.slice(frame, upper)
        .filter((img) => img?.cached === false)
        .map((img) => img?.onloadPromise);
    }

    /**
     * Handles playback of the image sequence
     * Image playback is based on framerate but will pause and wait for images to load
     * if the currently accessed image is not loaded during playback.
     */
    async function syncWithVideo(nextFrame: number): Promise<void> {
      if (data.playing) {
        if (nextFrame > data.maxFrame) {
          return pause();
        }
        // expectFrame is safe here because, even though this frame may never have been
        // seeked before, it is at MOST 1 frame away from a frame that has.
        // So the correct behavior of this function implicitly requires that seek()
        // always trigger caching for surrounding frames.
        const nextImage = expectFrame(nextFrame);
        if (!nextImage.cached) {
          // Prevents advancing the frame while playing if the current image is not loaded
          loadingVideo.value = true;
          await Promise.all(checkCached(nextFrame, local.playCache));
          loadingVideo.value = false;
          // A user interaction (pause, seek) could have happened during load.
          // Restart syncWithVideo() logic on same frame.  MUST return here to
          // prevent duplicating the loop.
          return syncWithVideo(data.frame + 1);
        }
        seek(nextFrame);
        setTimeout(() => syncWithVideo(data.frame + 1), 1000 / props.frameRate);
      }
      return undefined;
    }

    async function play() {
      try {
        data.playing = true;
        syncWithVideo(data.frame + 1);
      } catch (ex) {
        console.error(ex);
      }
    }

    const {
      cursorHandler,
      initializeViewer,
      mediaController,
    } = commonMedia.initialize({ seek, play, pause });

    if (local.imgs.length) {
      const imgInternal = cacheFrame(0);
      imgInternal.onloadPromise.then(() => {
        initializeViewer(imgInternal.image.naturalWidth, imgInternal.image.naturalHeight);
        const quadFeatureLayer = commonMedia.geoViewerRef.value.createLayer('feature', {
          features: ['quad'],
        });
        local.quadFeature = quadFeatureLayer.createFeature('quad');
        seek(0);
        data.ready = true;
      });
    }

    return {
      data,
      loadingVideo,
      loadingImage,
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
    class="video-annotator"
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
      :style="{ cursor: data.cursor }"
      @mousemove="cursorHandler.handleMouseMove"
      @mouseleave="cursorHandler.handleMouseLeave"
      @mouseover="cursorHandler.handleMouseEnter"
    >
      <div class="loadingSpinnerContainer">
        <v-progress-circular
          v-if="loadingVideo || loadingImage"
          class="loadingSpinner"
          indeterminate
          size="100"
          width="15"
          color="light-blue"
        >
          Loading
        </v-progress-circular>
      </div>
    </div>
    <slot
      ref="control"
      name="control"
      @resize="onResize"
    />
    <slot v-if="data.ready" />
  </div>
</template>

<style lang="scss" scoped>
@import "./annotator.scss";
</style>
