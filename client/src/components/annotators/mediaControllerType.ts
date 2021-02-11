import type { Ref } from '@vue/composition-api';

// https://en.wikipedia.org/wiki/Flick_(time)
export const Flick = 705_600_000;

export const NTSCFlickrates: Record<string, number> = {
  '24000/1001': 29429400,
  '30000/1001': 23543520,
  '60000/1001': 11771760,
  '120000/1001': 5885880,
};

/**
 * MediaController provides an interface for time and a few
 * other properties of the annotator window.
 *
 * See components/annotators/README.md for docs.
 */
export interface MediaController {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  geoViewerRef: Readonly<Ref<any>>;
  playing: Readonly<Ref<boolean>>;
  frame: Readonly<Ref<number>>;
  flick: Readonly<Ref<number | undefined>>;
  hasFlicks: Readonly<boolean>;
  filename: Readonly<Ref<string>>;
  maxFrame: Readonly<Ref<number>>;
  syncedFrame: Readonly<Ref<number>>;
  prevFrame(): void;
  nextFrame(): void;
  play(): void;
  pause(): void;
  seek(frame: number): void;
  resetZoom(): void;
  setCursor(c: string): void;
  setImageCursor(c: string): void;
}
