<script lang="ts">
import { join } from 'path';
import {
  computed, defineComponent, ref, Ref,
} from '@vue/composition-api';

import type { DatasetType, MultiCamImportArgs } from 'dive-common/apispec';
import type { MediaImportPayload } from 'platform/desktop/constants';

import ImportButton from 'dive-common/components/ImportButton.vue';
import ImportMultiCamDialog from 'dive-common/components/ImportMultiCamDialog.vue';
import * as api from '../api';
import { JsonMetaCache, recents, setRecents } from '../store/dataset';
import { setOrGetConversionJob } from '../store/jobs';
import BrowserLink from './BrowserLink.vue';
import NavigationBar from './NavigationBar.vue';
import ImportDialog from './ImportDialog.vue';


export default defineComponent({
  components: {
    BrowserLink,
    ImportButton,
    ImportDialog,
    NavigationBar,
    ImportMultiCamDialog,
  },

  setup(_, { root }) {
    const snackbar = ref(false);
    const importMultiCamDialog = ref(false);
    const pageSize = 12; // Default 12 looks good on default width/height of window
    const limit = ref(pageSize);
    const errorText = ref('');
    const pendingImportPayload: Ref<MediaImportPayload | null> = ref(null);
    const searchText: Ref<string | null> = ref('');
    const stereo = ref(false);
    const multiCamOpenType: Ref<'image-sequence'|'video'> = ref('image-sequence');

    async function open(dstype: DatasetType) {
      const ret = await api.openFromDisk(dstype);
      if (!ret.canceled) {
        try {
          pendingImportPayload.value = await api.importMedia(ret.filePaths);
        } catch (err) {
          snackbar.value = true;
          errorText.value = err.message;
        }
      }
    }

    /** Accept args from the dialog, as it may have modified some parts */
    async function finalizeImport(args: MediaImportPayload) {
      try {
        const jsonMeta = await api.finalizeImport(args);
        pendingImportPayload.value = null; // close dialog
        if (!jsonMeta.transcodingJobKey) {
          root.$router.push({
            name: 'viewer',
            params: { id: jsonMeta.id },
          });
        } else {
          // Display new data and await transcoding to complete
          const recentsMeta = await api.loadMetadata(jsonMeta.id);
          setRecents(recentsMeta);
        }
      } catch (err) {
        snackbar.value = true;
        errorText.value = err.message;
      }
    }

    function openMultiCamDialog(args: {stereo: boolean; openType: 'image-sequence' | 'video'}) {
      stereo.value = args.stereo;
      multiCamOpenType.value = args.openType;
      importMultiCamDialog.value = true;
    }

    async function multiCamImport(args: MultiCamImportArgs) {
      importMultiCamDialog.value = false;
      try {
        pendingImportPayload.value = await api.importMultiCam(args);
      } catch (err) {
        snackbar.value = true;
        errorText.value = err.message;
      }
    }

    const filteredRecents = computed(() => recents.value
      .filter((v) => v.name.toLowerCase().indexOf((searchText.value || '').toLowerCase()) >= 0));
    const paginatedRecents = computed(() => (filteredRecents.value.slice(0, limit.value)));
    const totalRecents = computed(() => filteredRecents.value.length);

    function toggleMore() {
      if (limit.value < recents.value.length) {
        limit.value = recents.value.length;
      } else {
        limit.value = pageSize;
      }
    }
    function getTypeIcon(recent: JsonMetaCache) {
      if (recent.type === 'multi') {
        if (recent.subType === 'stereo') {
          return 'mdi-binoculars';
        }
        return 'mdi-camera-burst';
      }
      if (recent.type === 'video') {
        return 'mdi-file-video';
      }
      return 'mdi-image-multiple';
    }

    return {
      // methods
      open,
      finalizeImport,
      multiCamImport,
      join,
      setOrGetConversionJob,
      toggleMore,
      openMultiCamDialog,
      getTypeIcon,
      importMedia: api.importMedia,
      // state
      multiCamOpenType,
      stereo,
      pageSize,
      limit,
      paginatedRecents,
      pendingImportPayload,
      totalRecents,
      searchText,
      snackbar,
      errorText,
      importMultiCamDialog,
    };
  },
});
</script>

<template>
  <v-main>
    <v-dialog
      :value="pendingImportPayload !== null || importMultiCamDialog"
      persistent
      width="800"
      overlay-opacity="0.95"
      max-width="80%"
    >
      <ImportDialog
        v-if="pendingImportPayload !== null"
        :import-data="pendingImportPayload"
        @finalize-import="finalizeImport($event)"
        @abort="pendingImportPayload = null"
      />
      <ImportMultiCamDialog
        v-if="importMultiCamDialog"
        :stereo="stereo"
        :data-type="multiCamOpenType"
        @begin-multicam-import="multiCamImport($event)"
        @abort="importMultiCamDialog = false"
      />
    </v-dialog>
    <navigation-bar />
    <v-container>
      <v-col>
        <v-row>
          <v-col
            md="8"
            sm="6"
          >
            <h1 class="text-h3 mb-4 font-weight-light">
              DIVE Annotation Tool
            </h1>
            <h3>Useful Links</h3>
            <div>
              <browser-link
                display="inline"
                href="https://kitware.github.io/dive/"
              >
                User Guide
              </browser-link>
            </div>
            <div>
              <browser-link
                display="inline"
                href="https://viame.kitware.com/#/collection/5e4c256ca0fc86aa03120c34"
              >
                Public example data
              </browser-link>
            </div>
            <div>
              <browser-link
                display="inline"
                href="https://viametoolkit.org/"
              >
                viametoolkit.org
              </browser-link>
            </div>
          </v-col>
          <v-col
            md="4"
            sm="6"
          >
            <import-button
              name="Open Image Sequence"
              icon="mdi-folder-open"
              open-type="image-sequence"
              class="my-2"
              @open="open($event)"
              @multi-cam="openMultiCamDialog"
            />
            <import-button
              name="Open Video"
              icon="mdi-file-video"
              open-type="video"
              class="my-2"
              @open="open($event)"
              @multi-cam="openMultiCamDialog"
            />
          </v-col>
        </v-row>
        <v-row>
          <v-card
            class="px-4 py-2 my-4"
            min-width="100%"
          >
            <div
              v-if="totalRecents > 0 || searchText"
              class="d-flex flex-row"
            >
              <div class="text-h4 font-weight-light mb-2">
                Recent
              </div>
              <v-spacer />
              <v-text-field
                v-model="searchText"
                dense
                outlined
                clearable
                hide-details
                placeholder="search"
                class="shrink"
                color="grey darken-1"
              >
                <template #append>
                  <v-icon
                    color="grey darken-1"
                  >
                    mdi-magnify
                  </v-icon>
                </template>
              </v-text-field>
            </div>
            <h2
              v-else
              class="text-h4 font-weight-light mb-2"
            >
              Open images or video to get started
            </h2>
            <div
              v-for="recent in paginatedRecents"
              :key="recent.id"
              class="pa-1"
            >
              <h3 class="text-body-1">
                <v-icon
                  class="pr-2"
                  color="primary lighten-2"
                >
                  {{ getTypeIcon(recent) }}
                </v-icon>
                <span v-if="setOrGetConversionJob(recent.id)">
                  <span class="primary--text text--darken-1 text-decoration-none">
                    {{ recent.name }}
                  </span>
                  <span class="pl-4">
                    Converting
                    <v-icon>
                      mdi-spin mdi-sync
                    </v-icon>
                  </span>
                </span>
                <router-link
                  v-else
                  :to="{ name: 'viewer', params: { id: recent.id } }"
                  class="primary--text text--lighten-3 text-decoration-none"
                >
                  {{ recent.name }}
                </router-link>
                <span class="grey--text px-4">
                  {{ recent.originalBasePath }}
                </span>
              </h3>
            </div>
            <div
              v-if="pageSize < totalRecents"
              class="mx-1"
            >
              <v-divider class="my-2" />
              <h3
                class="text-body-1"
                style="cursor: pointer;"
                @click="toggleMore"
              >
                <v-icon
                  class="pr-2"
                  color="primary lighten-3"
                >
                  {{ (limit === totalRecents) ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
                </v-icon>
                <span
                  class="primary--text text--lighten-3"
                >
                  <span v-if="limit < totalRecents">
                    Show {{ totalRecents - pageSize }} more
                  </span>
                  <span v-else>
                    Show less
                  </span>
                </span>
              </h3>
            </div>
          </v-card>
        </v-row>
      </v-col>
    </v-container>
    <v-snackbar
      v-model="snackbar"
      :timeout="-1"
      color="error"
    >
      {{ errorText }}
      <template v-slot:action="{ attrs }">
        <v-btn
          text
          v-bind="attrs"
          @click="snackbar = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </v-main>
</template>

<style lang="scss">
</style>
