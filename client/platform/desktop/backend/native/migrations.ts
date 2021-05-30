/* eslint-disable no-param-reassign */
import { JsonMeta, JsonMetaCurrentVersion } from 'platform/desktop/constants';

function upgrade(meta: JsonMeta) {
  if (meta.version === JsonMetaCurrentVersion) {
    /* Perform soft upgrades of backward-compatible properties */
    if (meta.originalFps === undefined) {
      // This will be an incorrect value.
      meta.originalFps = meta.fps;
    }
    if (meta.multiCam === undefined) {
      meta.multiCam = null;
    }
  } else if (meta.version < JsonMetaCurrentVersion) {
    /* Perform major version upgrade */
    console.error('Impossible schema', meta);
    throw new Error('Impossible schema revision detected.  This is not a valid DIVE project metadata file.  Check the console for details.');
  } else if (meta.version > JsonMetaCurrentVersion) {
    throw new Error('You are trying to open a newer version of the project schema.  Please upgrade DIVE to the latest version');
  }
  meta.version = JsonMetaCurrentVersion;
}

// eslint-disable-next-line import/prefer-default-export
export { upgrade };
