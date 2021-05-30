import { Api } from 'dive-common/apispec';
import * as api from 'platform/desktop/frontend/api';

/* Warning, this import involves node.js code for loadDetections (below) */
import * as common from 'platform/desktop/backend/native/common';

import { settings } from './settings';
import { load, setRecents } from './dataset';

/* Run forward migrations on any client-side data stores */
export async function migrate() {
  /* No migrations yet */
  await load();
}

/**
 * Wrap API with hooks to use the store
 */
export default function wrap(): Api {
  async function loadMetadata(datasetId: string) {
    const meta = await api.loadMetadata(encodeURIComponent(datasetId));
    // Only if not multi
    if (!datasetId.includes('/')) {
      setRecents(meta);
    }
    return meta;
  }

  /**
   * loadDetections loads JSON data directly from disk into the
   * renderer thread. It relies on the node runtime being enabled on the browser.
   *
   * This is done such that large annotation files do not need to be loaded into memory
   * twice, serialized and deserialized twice, and transmitted over the local network.
   *
   * In a future version, this could me moved to the backend and streamed directly
   * to the client using something like https://github.com/uhop/stream-json
   */
  async function loadDetections(datasetId: string) {
    return common.loadDetections(settings.value, datasetId);
  }

  return {
    ...api,
    loadDetections,
    loadMetadata,
  };
}
