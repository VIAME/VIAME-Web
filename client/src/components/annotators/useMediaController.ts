// Reference used because of https://github.com/Microsoft/TypeScript/issues/28502
/// <reference types="resize-observer-browser" />
import geo from 'geojs';
import { throttle } from 'lodash';
import {
  ref, reactive, onMounted, onBeforeUnmount, provide, toRef, Ref,
} from '@vue/composition-api';
import { use } from 'vue-media-annotator/provides';

import type { MediaController } from './mediaControllerType';

const MediaControllerSymbol = Symbol('media-controller');

export function injectMediaController() {
  return use<MediaController>(MediaControllerSymbol);
}

export default function useMediaController({ emit }: {
  emit(name: string, val: unknown): void;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const geoViewerRef: Ref<any> = ref(undefined);
  const containerRef: Ref<HTMLElement | undefined> = ref(undefined);
  const imageCursorRef: Ref<HTMLElement | undefined> = ref(undefined);

  const data = reactive({
    ready: false,
    playing: false,
    frame: 0,
    trueVideoFrame: 0,
    filename: '',
    lockedCamera: false,
    currentTime: 0,
    duration: 0,
    volume: 0,
    speed: 1.0,
    maxFrame: 0,
    syncedFrame: 0,
    observer: null,
    cursor: 'default',
    imageCursor: '',
    originalBounds: {
      left: 0,
      top: 0,
      bottom: 1,
      right: 1,
    },
  });

  const emitFrame = throttle(() => {
    emit('frame-update', data.frame);
  }, 200);

  function onResize() {
    if (geoViewerRef.value === undefined || containerRef.value === undefined) {
      return;
    }
    const size = containerRef.value.getBoundingClientRect();
    const mapSize = geoViewerRef.value.size();
    if (size.width !== mapSize.width || size.height !== mapSize.height) {
      window.requestAnimationFrame(() => {
        geoViewerRef.value.size(size);
      });
    }
  }

  function resetZoom() {
    const zoomAndCenter = geoViewerRef.value.zoomAndCenterFromBounds(
      data.originalBounds, 0,
    );
    geoViewerRef.value.zoom(zoomAndCenter.zoom);
    geoViewerRef.value.center(zoomAndCenter.center);
  }

  function toggleLockedCamera() {
    data.lockedCamera = !data.lockedCamera;
  }

  function resetMapDimensions(width: number, height: number, margin = 0.3) {
    geoViewerRef.value.bounds({
      left: 0,
      top: 0,
      bottom: height,
      right: width,
    });
    const params = geo.util.pixelCoordinateParams(
      containerRef.value, width, height, width, height,
    );
    const { right, bottom } = params.map.maxBounds;
    data.originalBounds = params.map.maxBounds;
    geoViewerRef.value.maxBounds({
      left: 0 - (right * margin),
      top: 0 - (bottom * margin),
      right: right * (1 + margin),
      bottom: bottom * (1 + margin),
    });
    geoViewerRef.value.zoomRange({
      // do not set a min limit so that bounds clamping determines min
      min: -Infinity,
      // 4x zoom max
      max: 4,
    });
    geoViewerRef.value.clampBoundsX(true);
    geoViewerRef.value.clampBoundsY(true);
    geoViewerRef.value.clampZoom(true);
    resetZoom();
  }

  let observer: ResizeObserver | null = null;
  onMounted(() => {
    if (containerRef.value) {
      observer = new ResizeObserver(onResize);
      observer.observe(containerRef.value);
    } else {
      throw new Error('Container was missing, could not register observer');
    }
  });
  onBeforeUnmount(() => {
    if (containerRef.value && observer !== null) {
      observer.unobserve(containerRef.value);
    } else {
      throw new Error('Container or observer was missing');
    }
  });

  /**
   * This secondary initialization wrapper solves a sort of
   * chicken-and-egg problem, allowing the function consumer to use
   * the state above to construct the dependencies for the methods below.
   */
  function initialize({
    seek, play, pause, setVolume, setSpeed,
  }: {
    seek(frame: number): void;
    play(): void;
    pause(): void;
    setVolume?(level: number): void;
    setSpeed?(level: number): void;
  }) {
    function setCursor(newCursor: string) {
      data.cursor = `${newCursor}`;
    }

    function setImageCursor(newCursor: string) {
      data.imageCursor = `${newCursor}`;
    }

    function centerOn(coords: { x: number; y: number; z: number }) {
      geoViewerRef.value.center(coords);
    }

    function initializeViewer(width: number, height: number) {
      const params = geo.util.pixelCoordinateParams(
        containerRef.value, width, height, width, height,
      );
      geoViewerRef.value = geo.map(params.map);
      resetMapDimensions(width, height);
      const interactorOpts = geoViewerRef.value.interactor().options();
      interactorOpts.keyboard.focusHighlight = false;
      interactorOpts.keyboard.actions = {};
      interactorOpts.click.cancelOnMove = 5;

      interactorOpts.actions = [
        interactorOpts.actions[0],
        // The action below is needed to have GeoJS use the proper handler
        // with cancelOnMove for right clicks
        {
          action: geo.geo_action.select,
          input: { right: true },
          name: 'button edit',
          owner: 'geo.MapInteractor',
        },
        // The action below adds middle mouse button click to panning
        // It allows for panning while in the process of polygon editing or creation
        {
          action: geo.geo_action.pan,
          input: 'middle',
          modifiers: { shift: false, ctrl: false },
          owner: 'geo.mapInteractor',
          name: 'button pan',

        },
        interactorOpts.actions[2],
        interactorOpts.actions[6],
        interactorOpts.actions[7],
        interactorOpts.actions[8],
        interactorOpts.actions[9],
      ];
      // Set > 2pi to disable rotation
      interactorOpts.zoomrotateMinimumRotation = 7;
      interactorOpts.zoomAnimation = {
        enabled: false,
      };
      interactorOpts.momentum = {
        enabled: false,
      };
      interactorOpts.wheelScaleY = 0.2;
      geoViewerRef.value.interactor().options(interactorOpts);
    }

    function prevFrame() {
      const targetFrame = data.frame - 1;
      if (targetFrame >= 0) {
        seek(targetFrame);
      }
    }

    function nextFrame() {
      const targetFrame = data.frame + 1;
      if (targetFrame <= data.maxFrame) {
        seek(targetFrame);
      }
    }

    const cursorHandler = {
      handleMouseLeave() {
        if (imageCursorRef.value) {
          imageCursorRef.value.style.display = 'none';
        }
      },
      handleMouseEnter() {
        if (imageCursorRef.value) {
          imageCursorRef.value.style.display = 'block';
        }
      },
      handleMouseMove(evt: MouseEvent) {
        const offsetX = evt.clientX + 10;
        const offsetY = evt.clientY - 25;
        window.requestAnimationFrame(() => {
          if (imageCursorRef.value) {
            imageCursorRef.value.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
          }
        });
      },
    };

    const mediaController = {
      geoViewerRef,
      playing: toRef(data, 'playing'),
      frame: toRef(data, 'frame'),
      trueVideoFrame: toRef(data, 'trueVideoFrame'),
      filename: toRef(data, 'filename'),
      lockedCamera: toRef(data, 'lockedCamera'),
      currentTime: toRef(data, 'currentTime'),
      duration: toRef(data, 'duration'),
      volume: toRef(data, 'volume'),
      maxFrame: toRef(data, 'maxFrame'),
      speed: toRef(data, 'speed'),
      syncedFrame: toRef(data, 'syncedFrame'),
      prevFrame,
      nextFrame,
      play,
      pause,
      seek,
      resetZoom,
      toggleLockedCamera,
      centerOn,
      setCursor,
      setImageCursor,
      setVolume,
      setSpeed,
    } as MediaController;

    provide(MediaControllerSymbol, mediaController);

    return {
      cursorHandler,
      initializeViewer,
      mediaController,
    };
  }

  return {
    containerRef,
    data,
    emitFrame,
    geoViewerRef,
    imageCursorRef,
    initialize,
    onResize,
    resetMapDimensions,
  };
}
