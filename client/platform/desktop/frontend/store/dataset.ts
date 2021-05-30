import Vue from 'vue';
import Install, { ref, computed } from '@vue/composition-api';
import { JsonMeta } from 'platform/desktop/constants';
import { DatasetType, SubType } from 'dive-common/apispec';

const RecentsKey = 'desktop.recent';

// TODO remove this: this won't be necessary in Vue 3
Vue.use(Install);

/**
 * JsonMetaCache is a subset of JsonMeta
 * cached in localStorage for quickly listing
 * known datasets
 */
export interface JsonMetaCache {
  version: number;
  type: DatasetType | 'multi';
  id: string;
  fps: number;
  name: string;
  createdAt: string;
  originalBasePath: string;
  originalVideoFile: string;
  transcodedVideoFile?: string;
  subType: SubType;
}

/**
 * Handle migration for changes in JsonMetaCache schema
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function hydrateJsonMetaCacheValue(input: any): JsonMetaCache {
  return {
    originalVideoFile: '',
    transcodedVideoFile: '',
    subType: null,
    ...input,
  };
}

const datasets = ref({} as Record<string, JsonMetaCache>);

const recents = computed(() => {
  const list = Object.values(datasets.value)
    .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
  return list;
});

/**
 * Load recent datasets from localstorage.
 *
 * Note that the localStorage copy is just a cache and not a source of truth.
 * The real dataset JsonMeta must be loaded from disk through the
 * loadMetadata() backend method.
 */
function load(): JsonMetaCache[] {
  try {
    const arr = window.localStorage.getItem(RecentsKey);
    if (arr) {
      const maybeArr = JSON.parse(arr);
      if (maybeArr.length) {
        maybeArr.forEach((meta: JsonMetaCache) => (
          Vue.set(datasets.value, meta.id, hydrateJsonMetaCacheValue(meta))
        ));
        return maybeArr;
      }
    }
    return [];
  } catch (err) {
    throw new Error(`could not load meta from localstorage: ${err}`);
  }
}

function locateDuplicates(meta: JsonMeta) {
  return recents.value.filter((candidate) => (
    candidate.originalBasePath === meta.originalBasePath
    && (
      meta.type === 'video'
        ? meta.originalVideoFile === candidate.originalVideoFile
        : true
    )
  ));
}

/**
 * Add ID to recent datasets
 * @param id dataset id path
 */
function setRecents(meta: JsonMeta) {
  Vue.set(datasets.value, meta.id, {
    version: meta.version,
    type: meta.type,
    id: meta.id,
    fps: meta.fps,
    name: meta.name,
    createdAt: meta.createdAt,
    originalBasePath: meta.originalBasePath,
    originalVideoFile: meta.originalVideoFile,
    transcodedVideoFile: meta.transcodedVideoFile,
    subType: meta.subType,
  } as JsonMetaCache);
  const values = Object.values(datasets.value);
  window.localStorage.setItem(RecentsKey, JSON.stringify(values));
}

function clearRecents() {
  datasets.value = {};
  window.localStorage.setItem(RecentsKey, JSON.stringify([]));
}

export {
  datasets,
  recents,
  load,
  locateDuplicates,
  setRecents,
  clearRecents,
};
