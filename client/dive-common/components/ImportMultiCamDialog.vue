<script lang="ts">
import Vue from 'vue';
import {
  computed, defineComponent, ref, Ref, PropType,
} from '@vue/composition-api';
import { filterByGlob } from 'platform/desktop/sharedUtils';
import {
  CustomMediaImportPayload,
  DatasetType,
  HTMLFileReferences,
  useApi,
} from 'dive-common/apispec';

import ImportMultiCamAddType from 'dive-common/components/ImportMultiCamAddType.vue';


export default defineComponent({
  components: {
    ImportMultiCamAddType,
  },
  name: 'ImportMultiCamDialog',
  props: {
    stereo: {
      type: Boolean as PropType<boolean>,
      required: false,
    },
    dataType: {
      type: String as PropType<'image-sequence' | 'video'>,
      default: 'image-sequence',
    },
  },
  setup(props, { emit }) {
    const { openFromDisk, importMedia } = useApi();
    const importType: Ref<'multi'|'keyword'| ''> = ref('');
    const folderList: Ref<Record<string, string>> = ref({});
    const keywordFolder = ref('');
    const pendingImportPayload: Ref<CustomMediaImportPayload | null> = ref(null);
    const globList: Ref<Record<string, string>> = ref({});
    const calibrationFile = ref('');
    const defaultDisplay = ref('left');
    const addNewToggle = ref(false);
    const newSetName = ref('');

    const htmlFileReferences: HTMLFileReferences = {
      mediaHTMLFileList: {},
    }; //Used to store fileReferences for Web version
    if (props.stereo) {
      folderList.value = {
        left: '',
        right: '',
      };
      globList.value = {
        left: '',
        right: '',
      };
    }
    if (props.dataType === 'video') {
      importType.value = 'multi';
    }

    const displayKeys = computed(() => {
      if (importType.value === 'multi') return Object.keys(folderList.value);
      if (importType.value === 'keyword') return Object.keys(globList.value);
      return [];
    });

    const filteredImages = computed(() => {
      const filtered: Record<string, string[]> = {};
      Object.entries(globList.value).forEach(([key, glob]) => {
        if (pendingImportPayload.value) {
          filtered[key] = filterByGlob(
            glob, pendingImportPayload.value.jsonMeta.originalImageFiles,
          );
        }
      });
      return filtered;
    });

    const keywordReady = computed(() => {
      const entries = Object.entries(filteredImages.value);
      let length = -1;
      let totalList: string[] = [];
      if (!entries.length) {
        return 'Need to have some data loaded';
      }
      for (let i = 0; i < entries.length; i += 1) {
        const imageEntry = entries[i];
        if (!imageEntry[1].length) {
          return `Requires filtered Images for ${imageEntry[0]} `;
        } if (length === -1) {
          length = imageEntry[1].length;
        }
        if (length !== imageEntry[1].length) {
          return `All glob patterns should have the same length of ${length}`;
        }
        if (
          imageEntry[1].filter(
            // eslint-disable-next-line no-loop-func
            (value: string) => totalList.includes(value),
          ).length
        ) {
          return 'Intersecting values.  Images must be unique to globs';
        }
        totalList = totalList.concat(imageEntry[0]);
      }
      return 'Success';
    });

    const nextSteps = computed(() => {
      if (importType.value === 'multi') {
        const entries = Object.entries(folderList.value);
        const filterLength = entries.filter(([, val]) => val !== '').length;
        if (entries.length === filterLength && entries.length) {
          return true;
        }
        return false;
      }
      if (importType.value === 'keyword' && keywordFolder.value && keywordReady.value === 'Success') {
        return true;
      }
      return false;
    });

    async function open(dstype: DatasetType | 'calibration', folder: string | 'calibration') {
      const ret = await openFromDisk(dstype, dstype === 'image-sequence');
      if (!ret.canceled) {
        try {
          const path = ret.filePaths[0];
          if (folder === 'calibration') {
            calibrationFile.value = path;
            if (ret.fileList?.length) {
              [htmlFileReferences.calibrationHTMLFile] = ret.fileList;
            }
          } else if (importType.value === 'multi') {
            if (ret.root) {
              folderList.value[folder] = ret.root;
            } else {
              folderList.value[folder] = path;
            }
            if (ret.fileList) {
              htmlFileReferences.mediaHTMLFileList[folder] = ret.fileList;
            }
          } else if (importType.value === 'keyword') {
            [keywordFolder.value] = ret.filePaths;
            if (ret.root) {
              keywordFolder.value = ret.root;
            }
            pendingImportPayload.value = await importMedia(ret.filePaths);
            if (ret.fileList) {
              htmlFileReferences.mediaHTMLFileList[folder] = ret.fileList;
            }
          }
        } catch (err) {
          console.error(err);
        }
      }
    }

    const deleteSet = (key: string) => {
      if (importType.value === 'multi') {
        if (!folderList.value[key]) {
          Vue.delete(folderList.value, key);
        }
      } else if (importType.value === 'keyword') {
        if (!globList.value[key]) {
          Vue.delete(globList.value, key);
        }
      }
    };
    const addNewSet = (name: string) => {
      if (importType.value === 'multi') {
        if (!folderList.value[name]) {
          Vue.set(folderList.value, name, '');
        }
      } else if (importType.value === 'keyword') {
        if (!globList.value[newSetName.value]) {
          Vue.set(globList.value, name, '');
        }
      }
      newSetName.value = '';
      addNewToggle.value = false;
    };

    const prepForImport = () => {
      if (importType.value === 'multi') {
        emit('begin-multicam-import', {
          defaultDisplay: defaultDisplay.value,
          folderList: folderList.value,
          calibrationFile: calibrationFile.value,
          type: props.dataType,
          htmlFileReferences,
        });
      } else if (importType.value === 'keyword') {
        emit('begin-multicam-import', {
          defaultDisplay: defaultDisplay.value,
          keywordFolder: keywordFolder.value,
          globList: globList.value,
          calibrationFile: calibrationFile.value,
          type: 'image-sequence',
          htmlFileReferences,
        });
      }
    };
    return {
      keywordReady,
      nextSteps,
      importType,
      folderList,
      keywordFolder,
      pendingImportPayload,
      globList,
      filteredImages,
      calibrationFile,
      defaultDisplay,
      displayKeys,
      addNewToggle,
      newSetName,
      //Methods
      open,
      prepForImport,
      addNewSet,
      deleteSet,
    };
  },
});
</script>

<template>
  <v-card
    outlined
    class="import-card"
    style="overflow-x: hidden;"
  >
    <v-card-title class="text-h5">
      Import {{ stereo ? 'Stereo' : 'MultiCam' }} Dataset
    </v-card-title>
    <v-card-text>
      <div v-if="dataType === 'image-sequence'">
        Please Select an import type.
        <v-radio-group v-model="importType">
          <v-radio
            value="multi"
            :label="
              `Multi-Folder: Import a left and right
             ${dataType === 'image-sequence' ? 'folder' : 'videos'}`"
          />
          <v-radio
            value="keyword"
            :label="
              `Keyword Filter: Use a filter to deteremine
             left and right ${dataType === 'image-sequence' ? 'images' : 'videos'}`"
          />
        </v-radio-group>
      </div>
      <div v-if="importType === 'multi'">
        <v-list>
          <v-list-item
            v-for="(item, key) in folderList"
            :key="key"
          >
            <v-btn
              v-if="!stereo"
              class="mr-2"
              color="error"
              @click="deleteSet(key)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
            <v-text-field
              :label="`${key}:`"
              :placeholder="dataType === 'image-sequence' ? 'Choose Folder' : 'Choose Video' "
              disabled
              :value="folderList[key]"
              class="mx-4"
            />
            <v-btn
              color="primary"
              @click="open(dataType, key)"
            >
              {{ dataType === 'image-sequence' ? 'Open Image Sequence' : 'Open Video' }}
              <v-icon class="ml-2">
                {{ dataType === 'image-sequence' ? 'mdi-folder-open' : 'mdi-file-video' }}
              </v-icon>
            </v-btn>
          </v-list-item>
          <v-list-item v-if="!stereo">
            <v-btn
              x-small
              color="primary"
              :disabled="addNewToggle"
              @click="addNewToggle = true"
            >
              <v-icon>
                mdi-plus
              </v-icon>
            </v-btn>
            <import-multi-cam-add-type
              v-if="addNewToggle"
              :name-list="displayKeys"
              @add-new="addNewSet"
              @cancel="addNewToggle = false"
            />
          </v-list-item>
        </v-list>
      </div>
      <div v-if="importType ==='keyword'">
        <v-list-item>
          Folder:
          <v-text-field
            label="Folder:"
            placeholder="Choose Folder"
            disabled
            :value="keywordFolder"
            class="mx-4"
          />
          <v-btn
            color="primary"
            @click="open('image-sequence', 'keyword')"
          >
            Open Image Sequence
            <v-icon class="ml-2">
              mdi-folder-open
            </v-icon>
          </v-btn>
        </v-list-item>
        <v-list-item
          v-for="(item, key) in globList"
          :key="key"
        >
          <v-btn
            v-if="!stereo"

            class="mr-2 mb-5"
            color="error"
            @click="deleteSet(key)"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
          <v-text-field
            v-model="globList[key]"
            :label="`${key} Glob Filter Pattern `"
            placeholder="Leave blank to use all images. example: *.png"
            persistent-hint
            outlined
            dense
          />
          <v-chip
            v-if="globList[key]"
            :color="filteredImages[key].length ? 'success' : 'error'"
            outlined
            class="ml-3 mb-5"
          >
            "{{ globList[key] }}" matches {{ filteredImages[key].length }}
            out of {{ pendingImportPayload.jsonMeta.originalImageFiles.length }} images
          </v-chip>
        </v-list-item>
        <v-list-item
          v-if="keywordFolder && keywordReady !== 'Success'"
        >
          <v-alert
            type="error"
            outlined
            dense
          >
            {{ keywordReady }}
          </v-alert>
        </v-list-item>
        <v-list-item v-if="!stereo">
          <v-btn
            x-small
            color="primary"
            :disabled="addNewToggle"
            @click="addNewToggle = true"
          >
            <v-icon>
              mdi-plus
            </v-icon>
          </v-btn>
          <import-multi-cam-add-type
            v-if="addNewToggle"
            :name-list="displayKeys"
            @add-new="addNewSet"
            @cancel="addNewToggle = false"
          />
        </v-list-item>
      </div>
      <div v-if="nextSteps">
        <v-alert
          type="info"
          outlined
          dense
        >
          Visualization currently doesn't support multi views so please choose
          a list of images to display by default when viewing
        </v-alert>
        <v-list>
          <v-list-item>
            Default Display:
            <v-radio-group v-model="defaultDisplay">
              <v-radio
                v-for="(item,index) in displayKeys"
                :key="index"
                :value="item"
                :label="item"
              />
            </v-radio-group>
          </v-list-item>
          <v-list-item v-if="stereo">
            Calibration File:
            <v-text-field
              label="Calibration File:"
              placeholder="Choose File"
              disabled
              :value="calibrationFile"
              class="mx-4"
            />
            <v-btn
              color="primary"
              @click="open('calibration', 'calibration')"
            >
              Open Calibration File
              <v-icon class="ml-2">
                mdi-matrix
              </v-icon>
            </v-btn>
          </v-list-item>
        </v-list>
      </div>
      <div class="d-flex flex-row mt-4">
        <v-spacer />
        <v-btn
          text
          outlined
          class="mr-5"
          @click="$emit('abort')"
        >
          Cancel
        </v-btn>
        <v-btn
          color="primary"
          :disabled="!nextSteps || (stereo && !calibrationFile)"
          @click="prepForImport"
        >
          Begin Import
        </v-btn>
      </div>
    </v-card-text>
  </v-card>
</template>

<style lang="scss" scoped>
@import 'dive-common/components/styles/KeyValueTable.scss';
</style>
