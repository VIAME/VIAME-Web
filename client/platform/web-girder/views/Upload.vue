<script lang='ts'>
import {
  defineComponent, Ref, ref, computed,
} from '@vue/composition-api';

import {
  ImageSequenceType, VideoType, DefaultVideoFPS, FPSOptions,
  inputAnnotationFileTypes, websafeVideoTypes, otherVideoTypes,
  websafeImageTypes, otherImageTypes,
} from 'dive-common/constants';

import ImportButton from 'dive-common/components/ImportButton.vue';
import ImportMultiCamDialog from 'dive-common/components/ImportMultiCamDialog.vue';
import { DatasetType, MultiCamImportFolderArgs, MultiCamImportKeywordArgs } from 'dive-common/apispec';
import { filterByGlob } from 'platform/desktop/sharedUtils';
import UploadGirder from './UploadGirder.vue';
import {
  validateUploadGroup, openFromDisk,
} from '../api/viame.service';


export interface InteralFiles {
  file: File;
  status: string | 'done' | 'pending' | 'error';
  progress: {
    indeterminate: boolean;
    current: number;
    size: number;
  };
  upload: null; //Mixin function
  result: null; //Mixin stuff
}

export interface PendingUpload {
  createSubFolders: boolean;
  name: string;
  files: InteralFiles[];
  meta: null | File;
  annotationFile: null | File;
  mediaList: File[];
  type: DatasetType | 'multi';
  fps: number;
  uploading: boolean;
    multiCam?: {
      folderList: Record<string, string[]>;
      calibrationFile?: string;
      defaultDisplay: string;
    };

}

interface GirderUpload {
  formatSize: (a: number) => string;
  totalProgress: number;
  totalProgressPercent: number;
  totalSize: number;
}

export default defineComponent({
  components: { ImportButton, ImportMultiCamDialog, UploadGirder },
  props: {
    location: {
      type: Object,
      required: true,
    },
    hideMeta: {
      type: Boolean,
      default: true, // TODO:  Once Meta upload is supported we can remove this
    },
  },
  setup(_, { emit }) {
    const preUploadErrorMessage: Ref<string | null> = ref(null);
    const pendingUploads: Ref<PendingUpload[]> = ref([]);
    const stereo = ref(false);
    const multiCamOpenType = ref('image-sequence');
    const importMultiCamDialog = ref(false);
    const girderUpload: Ref<null | GirderUpload> = ref(null);
    /**
     * Initial opening of file dialog
     */
    const openImport = async (dstype: DatasetType) => {
      const ret = await openFromDisk(dstype);
      if (!ret.canceled && ret.fileList) {
        // eslint-disable-next-line @typescript-eslint/no-use-before-define
        const processed = processImport(ret);
        if (processed?.fullList?.length === 0) return;
        if (processed && processed.fullList) {
          const name = processed.fullList.length === 1 ? processed.fullList[0].name : '';
          preUploadErrorMessage.value = null;
          try {
            // eslint-disable-next-line @typescript-eslint/no-use-before-define
            await addPendingUpload(
              name, processed.fullList, processed.metaFile,
              processed.annotationFile, processed.mediaList,
            );
          } catch (err) {
            preUploadErrorMessage.value = err;
          }
        }
      }
    };
    /**
     * Processes the imported media files to distinguish between
     * Media Files - Default files that aren't the Annotation or Meta
     * Annotation File - CSV or JSON file, or more in the future
     * Meta File - Right now a json file which has 'meta' in the name
     */
    const processImport = (files: {
      canceled: boolean; filePaths: string[]; fileList?: File[];
    }) => {
      //Check for auto files for meta and annotations
      const output: {
        annotationFile: null | File;
        metaFile: null | File;
        mediaList: File[];
        fullList: File[];
      } = {
        annotationFile: null,
        metaFile: null,
        mediaList: [],
        fullList: [],
      };
      const jsonFiles: [string, number][] = [];
      const csvFiles: [string, number][] = [];
      if (files.fileList) {
        files.filePaths.forEach((item, index) => {
          if (item.indexOf('.json') !== -1) {
            jsonFiles.push([item, index]);
          } else if (item.indexOf('.csv') !== -1) {
            csvFiles.push([item, index]);
          }
        });
        output.mediaList = files.fileList.filter((item) => (
          item.name.indexOf('.json') === -1 && item.name.indexOf('.csv') === -1));
        const metaIndex = jsonFiles.findIndex((item) => (item.indexOf('meta') !== -1));
        if (metaIndex !== -1) {
          output.metaFile = files.fileList[jsonFiles[metaIndex][1]];
        }
        if (jsonFiles.length === 1 && csvFiles.length === 0 && output.metaFile === null) {
          output.annotationFile = files.fileList[jsonFiles[0][1]];
        } else if (csvFiles.length && jsonFiles.length === 1) {
          if (jsonFiles[0][0].indexOf('meta') !== -1) {
            output.annotationFile = files.fileList[csvFiles[0][1]];
            output.metaFile = files.fileList[jsonFiles[0][1]];
          }
        } else if (jsonFiles.length > 1) {
          //Check for a meta
          const filtered = jsonFiles.filter((item) => (item.indexOf('meta') === -1));
          if (filtered.length === 1) {
            output.annotationFile = files.fileList[filtered[0][1]];
          }
        } else if (csvFiles.length) {
          output.annotationFile = files.fileList[csvFiles[0][1]];
        }
        output.fullList = [...output.mediaList];
        if (output.annotationFile) {
          output.fullList.push(output.annotationFile);
        }
        if (output.metaFile) {
          output.fullList.push(output.metaFile);
        }
      }
      return output;
    };
    const openMultiCamDialog = (args: { stereo: boolean; openType: 'image-sequence' | 'video' }) => {
      stereo.value = args.stereo;
      multiCamOpenType.value = args.openType;
      importMultiCamDialog.value = true;
    };
    const filterFileUpload = (type: DatasetType | 'meta' | 'annotation') => {
      if (type === 'meta') {
        return '.json';
      } if (type === 'annotation') {
        return inputAnnotationFileTypes.map((item) => `.${item}`).join(',');
      } if (type === 'video') {
        return websafeVideoTypes.concat(otherVideoTypes);
      }
      return websafeImageTypes.concat(otherImageTypes);
    };

    // TODO:  Implementation of initialization organization of multiCam files into a return
    // of the CustomMediaImportPayload defined in ImportMultiCamDialog.vue
    const multiCamImportCheck = (files: string[]) => ({
      jsonMeta: {
        originalImageFiles: files,
      },
      globPattern: '',
      mediaConvertList: [],
    });
    //TODO:  Implementation of the finalization of the Import.  Requires
    // Creation of an endpoint in the server which supports MultiCamImportArgs
    const multiCamImport = (args: MultiCamImportKeywordArgs | MultiCamImportFolderArgs) => {
      //Lets go through all files and modify any duplicates
      let mediaList: File[] = [];
      const folderList: Record<string, string[]> = {};
      if ((args as MultiCamImportKeywordArgs).globList !== undefined) {
        const keywordArgs = (args as MultiCamImportKeywordArgs);
        //We need to divide by glob list into different folders
        if (args.htmlFileReferences?.mediaHTMLFileList.keyword) {
          const { mediaHTMLFileList } = args.htmlFileReferences;
          mediaList = mediaList.concat(mediaHTMLFileList.keyword);
          Object.entries(keywordArgs.globList).forEach(([key, glob]) => {
            folderList[key] = filterByGlob(
              glob,
              mediaHTMLFileList.keyword.map((item) => item.name),
            );
          });
        }
      } else if (args.htmlFileReferences?.mediaHTMLFileList) {
        const { mediaHTMLFileList } = args.htmlFileReferences;
        Object.keys(mediaHTMLFileList).forEach((key) => {
          mediaList = mediaList.concat(mediaHTMLFileList[key]);
          folderList[key] = mediaHTMLFileList[key].map((item) => item.name);
        });
      }

      const calibrationFile = args.htmlFileReferences?.calibrationHTMLFile?.name;

      if (args.htmlFileReferences?.calibrationHTMLFile) {
        mediaList.push(args.htmlFileReferences.calibrationHTMLFile);
      }
      const fps = DefaultVideoFPS;
      //So now we take the args and modify the list of files we have to edit them
      preUploadErrorMessage.value = null;
      pendingUploads.value.push({
        createSubFolders: false,
        name: 'multi',
        files: [], //Will be set in the GirderUpload Component
        mediaList,
        meta: null,
        annotationFile: null,
        type: 'multi',
        fps,
        uploading: false,
        multiCam: {
          folderList,
          calibrationFile,
          defaultDisplay: args.defaultDisplay,
        },
      });
      importMultiCamDialog.value = false;
    };
    // Filter to show how many files are left to upload
    const filesNotUploaded = (item: PendingUpload) => item.files.filter(
      (file) => file.status !== 'done' && file.status !== 'error',
    ).length;
    // Processes the pending upload from the GirderUpload system to determine the progress
    const computeUploadProgress = (pendingUpload: PendingUpload) => {
      // use methods and properties from mixins
      if (girderUpload.value) {
        //Need to use the girderUpload ref to get these values out of the mixin
        const { formatSize, totalProgress, totalSize } = girderUpload.value;
        if (pendingUpload.files.length === 1 && !pendingUpload.uploading) {
          return formatSize(pendingUpload.files[0].progress.size);
        } if (pendingUpload.type === ImageSequenceType) {
          return `${filesNotUploaded(pendingUpload)} files`;
        } if (pendingUpload.type === VideoType && !pendingUpload.uploading) {
          return `${filesNotUploaded(pendingUpload)} videos`;
        } if (pendingUpload.type === VideoType && pendingUpload.uploading) {
          // For videos we display the total progress when uploading because
          // single videos can be large
          return `${formatSize(totalProgress)} of ${formatSize(totalSize)}`;
        }
        if (pendingUpload.type === 'multi') {
          return `${filesNotUploaded(pendingUpload)} files`;
        }
      }
      throw new Error(`could not determine adequate formatting for ${pendingUpload}`);
    };
    const getFilenameInputStateLabel = (pendingUpload: PendingUpload) => {
      const plural = pendingUpload.createSubFolders
        ? 's'
        : '';
      return `Folder Name${plural}`;
    };
    const getFilenameInputStateDisabled = (pendingUpload: PendingUpload) => (
      pendingUpload.uploading || pendingUpload.createSubFolders
    );
    const getFilenameInputStateHint = (pendingUpload: PendingUpload) => (
      pendingUpload.createSubFolders ? 'default folder names are used when "Create Subfolders" is selected' : ''
    );
    const addPendingUpload = async (
      name: string,
      allFiles: File[],
      meta: File | null,
      annotationFile: File | null,
      mediaList: File[],
    ) => {
      const resp = await validateUploadGroup(allFiles.map((f) => f.name));
      if (!resp.ok) {
        if (resp.message) {
          preUploadErrorMessage.value = resp.message;
        }
        throw new Error(resp.message);
      }
      const fps = resp.type === ImageSequenceType ? 5 : DefaultVideoFPS;
      const defaultFilename = resp.media[0];
      const validFiles = resp.media.concat(resp.annotations);
      // mapping needs to be done for the mixin upload functions
      const internalFiles = allFiles
        .filter((f) => validFiles.includes(f.name));
      let createSubFolders = false;
      if (resp.type === 'video') {
        if (resp.media.length > 1) {
          createSubFolders = true;
        }
      }
      pendingUploads.value.push({
        createSubFolders,
        name:
          internalFiles.length > 1
            ? defaultFilename.replace(/\..*/, '')
            : defaultFilename,
        files: [], //Will be set in the GirderUpload Component
        meta,
        annotationFile,
        mediaList,
        type: resp.type,
        fps,
        uploading: false,
      });
    };
    const remove = (pendingUpload: PendingUpload) => {
      const index = pendingUploads.value.indexOf(pendingUpload);
      pendingUploads.value.splice(index, 1);
    };
    function close() {
      emit('close');
    }
    function abort() {
      if (pendingUploads.value.length === 0) {
        close();
      }
    }
    const uploading = computed(() => pendingUploads.value.some((v) => v.uploading));
    const buttonAttrs = computed(() => {
      if (pendingUploads.value.length === 0) {
        return {
          block: true,
          color: 'primary',
          disabled: uploading.value,
        };
      }
      return {
        block: true,
        color: 'grey darken-3',
        depressed: true,
        disabled: uploading.value,
      };
    });
    return {
      buttonAttrs,
      FPSOptions,
      preUploadErrorMessage,
      pendingUploads,
      stereo,
      multiCamOpenType,
      importMultiCamDialog,
      girderUpload,
      uploading,
      //methods
      close,
      openImport,
      processImport,
      filterFileUpload,
      computeUploadProgress,
      getFilenameInputStateLabel,
      getFilenameInputStateDisabled,
      getFilenameInputStateHint,
      addPendingUpload,
      remove,
      // MultiCam Methods
      openMultiCamDialog,
      multiCamImportCheck,
      multiCamImport,
      abort,
    };
  },
});
</script>

<template>
  <div class="upload">
    <v-dialog
      :value="importMultiCamDialog"
      persistent
      overlay-opacity="0.95"
      max-width="80%"
    >
      <ImportMultiCamDialog
        v-if="importMultiCamDialog"
        :stereo="stereo"
        :data-type="multiCamOpenType"
        @begin-multicam-import="multiCamImport($event)"
        @abort="importMultiCamDialog = false; preUploadErrorMessage = null"
      />
    </v-dialog>
    <v-card
      outlined
      color="default"
    >
      <v-toolbar
        flat
        dark
      >
        <v-toolbar-title>Upload datasets</v-toolbar-title>
        <v-spacer />
        <v-btn
          icon
          @click="close"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-toolbar>
      <v-progress-linear
        v-show="girderUpload && girderUpload.totalProgressPercent"
        :value="girderUpload && girderUpload.totalProgressPercent"
        absolute
        height="6px"
      />
      <upload-girder
        ref="girderUpload"
        :pending-uploads="pendingUploads"
        :pre-upload-error-message="preUploadErrorMessage"
        :location="location"
        class="mx-6"
        @remove-upload="remove"
        @update:uploading="$emit('update:uploading', $event)"
        @abort="abort"
      >
        <template #default="{ upload }">
          <v-card
            v-for="(pendingUpload, i) of pendingUploads"
            :key="i"
            outlined
            class="pa-4 my-4"
          >
            <v-row class="align-center">
              <v-col class="py-0">
                <v-text-field
                  :value="pendingUpload.createSubFolders ? 'default' : pendingUpload.name"
                  class="upload-name"
                  :rules="[val => (val || '').length > 0 || 'This field is required']"
                  required
                  :label="getFilenameInputStateLabel(pendingUpload)"
                  :disabled="getFilenameInputStateDisabled(pendingUpload)"
                  :hint="getFilenameInputStateHint(pendingUpload)"
                  persistent-hint
                  @input="pendingUpload.name = $event"
                />
              </v-col>
              <v-col
                cols="3"
                class="py-0"
              >
                <v-select
                  v-model="pendingUpload.fps"
                  :items="FPSOptions"
                  :disabled="pendingUpload.uploading"
                  type="number"
                  required
                  label="FPS"
                  :append-icon="pendingUpload.annotationFile
                    ? 'mdi-alert' : 'mdi-chevron-down'"
                  :hint="pendingUpload.annotationFile
                    ? 'should match annotation fps' : 'annotation fps'"
                  persistent-hint
                />
              </v-col>
              <v-col
                cols="1"
                class="py-0"
              >
                <v-btn
                  icon
                  outlined
                  :disabled="pendingUpload.uploading"
                  @click="remove(pendingUpload)"
                >
                  <v-icon>mdi-close</v-icon>
                </v-btn>
              </v-col>
            </v-row>
            <v-row v-if="!pendingUpload.createSubFolders">
              <v-col class="py-0">
                <v-row v-if="!pendingUpload.createSubFolders && pendingUpload.type !== 'multi'">
                  <v-col>
                    <v-row>
                      <v-col>
                        <v-file-input
                          v-model="pendingUpload.mediaList"
                          label="Media Files"
                          multiple
                          :rules="[val => (val || '').length > 0 || 'Media Files are required']"
                          :accept="filterFileUpload(pendingUpload.type)"
                        />
                      </v-col>
                      <v-col>
                        <v-file-input
                          v-model="pendingUpload.annotationFile"
                          label="Annotation File"
                          hint="Optional"
                          :accept="filterFileUpload('annotation')"
                        />
                      </v-col>
                      <v-col v-if="!hideMeta">
                        <v-file-input
                          v-model="pendingUpload.meta"
                          label="Meta File"
                          hint="Optional"
                          :accept="filterFileUpload('meta')"
                        />
                      </v-col>
                    </v-row>
                  </v-col>
                </v-row>
              </v-col>
            </v-row>
            <span v-if="uploading">
              {{ computeUploadProgress(pendingUpload) }} remaining
            </span>
          </v-card>
          <div
            class="d-flex my-6"
            :class="{
              'flex-column': pendingUploads.length === 0,
            }"
          >
            <import-button
              :name="`Add ${pendingUploads.length ? 'Another ' : ''}Image Sequence`"
              icon="mdi-folder-open"
              open-type="image-sequence"
              class="grow"
              :class="[pendingUploads.length ? 'mr-3' : 'my-3']"
              :button-attrs="buttonAttrs"
              @open="openImport($event)"
              @multi-cam="openMultiCamDialog"
            />
            <import-button
              :name="`Add ${pendingUploads.length ? 'Another ' : ''}Video`"
              icon="mdi-file-video"
              class="grow"
              :class="[pendingUploads.length ? 'ml-3' : 'my-3']"
              open-type="video"
              :button-attrs="buttonAttrs"
              @open="openImport($event)"
              @multi-cam="openMultiCamDialog"
            />
          </div>
          <v-btn
            v-if="pendingUploads.length"
            :disabled="uploading"
            block
            large
            color="primary"
            class="my-6"
            @click="upload"
          >
            <v-icon class="pr-3">
              mdi-upload
            </v-icon>
            Start upload
          </v-btn>
        </template>
      </upload-girder>
    </v-card>
  </div>
</template>
