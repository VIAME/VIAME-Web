import Vue from 'vue';
import Install, { Ref, ref } from '@vue/composition-api';
import { ipcRenderer } from 'electron';
import { Settings } from 'platform/desktop/constants';

// TODO remove this: this won't be necessary in Vue 3
Vue.use(Install);

const SettingsKey = 'desktop.settings';

const settings: Ref<Settings | null> = ref(null);

function getDefaultSettings(): Promise<Settings> {
  return ipcRenderer.invoke('default-settings');
}

function validateSettings(s: Settings): Promise<string | boolean> {
  return ipcRenderer.invoke('validate-settings', s);
}

// Type Guard https://www.typescriptlang.org/docs/handbook/advanced-types.html
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isSettings(s: any): s is Settings {
  if (!s.version || typeof s.version !== 'number') {
    return false;
  }
  if (!s.viamePath || typeof s.viamePath !== 'string') {
    return false;
  }
  return true;
}

async function init() {
  const settingsStr = window.localStorage.getItem(SettingsKey);
  let settingsvalue = await getDefaultSettings();
  try {
    if (settingsStr) {
      const maybeSettings = JSON.parse(settingsStr);
      if (isSettings(maybeSettings)) {
        settingsvalue = {
          // Populate from defaults to include any missing properties
          ...settingsvalue,
          // Overwrite with explicitly persisted settings
          ...maybeSettings,
        };
      }
    }
  } catch {
    // pass
  }
  // finally, override any user settings with the values that have been
  // externally forced.
  if (settingsvalue.overrides.viamePath !== undefined) {
    settingsvalue.viamePath = settingsvalue.overrides.viamePath;
  }
  settings.value = settingsvalue;
  ipcRenderer.send('update-settings', settings.value);
}

function getSettings(): Settings {
  if (settings.value === null) {
    throw new Error('Settings requested before initialization!');
  }
  return settings.value;
}

async function setSettings(s: Settings) {
  window.localStorage.setItem(SettingsKey, JSON.stringify(s));
  ipcRenderer.send('update-settings', settings.value);
}

// Will be initialized on first import
init();

export {
  settings,
  getSettings,
  setSettings,
  validateSettings,
};
