<script lang="ts">
import {
  defineComponent, ref, computed, Ref,
} from '@vue/composition-api';
import type { Vue } from 'vue/types/vue';

/* VUE MEDIA ANNOTATOR */
import Track, { TrackId } from 'vue-media-annotator/track';
import {
  useAttributes,
  useLineChart,
  useStyling,
  useTrackFilters,
  useTrackSelectionControls,
  useTrackStore,
  useEventChart,
} from 'vue-media-annotator/use';
import { getTrack } from 'vue-media-annotator/use/useTrackStore';
import { provideAnnotator } from 'vue-media-annotator/provides';
import {
  ImageAnnotator,
  VideoAnnotator,
  LayerManager,
} from 'vue-media-annotator/components';
import { MediaController } from 'vue-media-annotator/components/annotators/mediaControllerType';

/* DIVE COMMON */
import PolygonBase from 'dive-common/recipes/polygonbase';
import HeadTail from 'dive-common/recipes/headtail';
import EditorMenu from 'dive-common/components/EditorMenu.vue';
import ConfidenceFilter from 'dive-common/components/ConfidenceFilter.vue';
import UserGuideButton from 'dive-common/components/UserGuideButton.vue';
import DeleteControls from 'dive-common/components/DeleteControls.vue';
import ControlsContainer from 'dive-common/components/ControlsContainer.vue';
import Sidebar from 'dive-common/components/Sidebar.vue';
import {
  useModeManager,
  useSave,
  useSettings,
} from 'dive-common/use';
import { useApi, FrameImage, DatasetType } from 'dive-common/apispec';
import { cloneDeep } from 'lodash';

export default defineComponent({
  components: {
    ControlsContainer,
    DeleteControls,
    Sidebar,
    LayerManager,
    VideoAnnotator,
    ImageAnnotator,
    ConfidenceFilter,
    UserGuideButton,
    EditorMenu,
  },

  // TODO: remove this in vue 3
  props: {
    id: {
      type: String,
      required: true,
    },
  },
  setup(props, ctx) {
    // TODO: eventually we will have to migrate away from this style
    // and use the new plugin pattern:
    // https://vue-composition-api-rfc.netlify.com/#plugin-development
    const prompt = ctx.root.$prompt;
    const loadError = ref('');
    const playbackComponent = ref(undefined as Vue | undefined);
    const currentId: Ref<string> = ref(props.id); // CurrentId, but used for resetting for multiCam
    const multiCamList: Ref<string[]> = ref([]);
    const defaultCamera: Ref<string> = ref('');
    const mediaController = computed(() => {
      if (playbackComponent.value) {
        // TODO: Bug in composition-api types incorrectly organizes the static members of a Vue
        // instance when using typeof ImageAnnotator, so we can't use the "real" type here
        // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
        // @ts-ignore
        return playbackComponent.value.mediaController as MediaController;
      }
      return {} as MediaController;
    });
    const frameRate = ref(null as number | null);
    const imageData = ref([] as FrameImage[]);
    const datasetType: Ref<DatasetType> = ref('image-sequence');
    const datasetName = ref('');
    const videoUrl = ref(undefined as undefined | string);
    const frame = ref(0); // the currently displayed frame number
    const { loadDetections, loadMetadata, saveMetadata } = useApi();
    // Loaded flag prevents annotator window from populating
    // with stale data from props, for example if a persistent store
    // like vuex is used to drive them.
    const loaded = ref(false);

    const {
      save: saveToServer,
      markChangesPending,
      pendingSaveCount,
    } = useSave(currentId);

    const recipes = [
      new PolygonBase(),
      new HeadTail(),
    ];

    const {
      typeStyling,
      stateStyling,
      updateTypeStyle,
      populateTypeStyles,
      getTypeStyles,
    } = useStyling({ markChangesPending });

    const {
      attributesList: attributes,
      loadAttributes,
      setAttribute,
      deleteAttribute,
    } = useAttributes({ markChangesPending });

    const {
      trackMap,
      sortedTracks,
      intervalTree,
      addTrack,
      insertTrack,
      removeTrack,
      getNewTrackId,
      removeTrack: tsRemoveTrack,
      clearAllTracks,
    } = useTrackStore({ markChangesPending });

    const {
      checkedTrackIds,
      checkedTypes,
      confidenceThreshold,
      confidenceFilters,
      allTypes,
      importTypes,
      usedTypes,
      filteredTracks,
      enabledTracks,
      populateConfidenceFilters,
      updateTypeName,
      removeTypeTracks,
      deleteType,
      updateCheckedTypes,
      updateCheckedTrackId,
    } = useTrackFilters({
      sortedTracks,
      removeTrack,
      markChangesPending,
    });

    const {
      selectedTrackId,
      selectTrack,
      editingTrack,
      selectNextTrack,
    } = useTrackSelectionControls({
      filteredTracks,
    });

    const { clientSettings, updateNewTrackSettings, updateTypeSettings } = useSettings(allTypes);

    // Provides wrappers for actions to integrate with settings
    const {
      mergeList,
      mergeInProgress,
      selectedFeatureHandle,
      handler,
      editingMode,
      visibleModes,
      selectedKey,
    } = useModeManager({
      recipes,
      selectedTrackId,
      editingTrack,
      frame,
      trackMap,
      mediaController,
      newTrackSettings: clientSettings.newTrackSettings.value,
      selectTrack,
      selectNextTrack,
      addTrack,
      removeTrack,
    });

    const allSelectedIds = computed(() => {
      const selected = selectedTrackId.value;
      if (selected !== null) {
        return mergeList.value.concat(selected);
      }
      return mergeList.value;
    });

    const { lineChartData } = useLineChart({
      enabledTracks, typeStyling, allTypes,
    });

    const { eventChartData } = useEventChart({
      enabledTracks, selectedTrackIds: allSelectedIds, typeStyling,
    });

    async function trackSplit(trackId: TrackId | null, _frame: number) {
      if (typeof trackId === 'number') {
        const track = getTrack(trackMap, trackId);
        let newtracks: [Track, Track];
        try {
          newtracks = track.split(_frame, getNewTrackId(), getNewTrackId() + 1);
        } catch (err) {
          await prompt({
            title: 'Error while splitting track',
            text: err,
            positiveButton: 'OK',
          });
          return;
        }
        const result = await prompt({
          title: 'Confirm',
          text: 'Do you want to split the selected track?',
          confirm: true,
        });
        if (!result) {
          return;
        }
        const wasEditing = editingTrack.value;
        handler.trackSelect(null);
        tsRemoveTrack(trackId);
        insertTrack(newtracks[0]);
        insertTrack(newtracks[1]);
        handler.trackSelect(newtracks[1].trackId, wasEditing);
      }
    }

    async function save() {
      // If editing the track, disable editing mode before save
      if (editingTrack.value) {
        handler.trackSelect(selectedTrackId.value, false);
      }
      try {
        await saveToServer({
          customTypeStyling: getTypeStyles(allTypes),
        });
      } catch (err) {
        let text = 'Unable to Save Data';
        if (err.response && err.response.status === 403) {
          text = 'You do not have permission to Save Data to this Folder.';
        }
        await prompt({
          title: 'Error while Saving Data',
          text,
          positiveButton: 'OK',
        });
        throw err;
      }
    }

    function saveThreshold() {
      saveMetadata(currentId.value, {
        confidenceFilters: confidenceFilters.value,
      });
    }

    // Navigation Guards used by parent component
    async function warnBrowserExit(event: BeforeUnloadEvent) {
      if (pendingSaveCount.value === 0) return;
      event.preventDefault();
      // eslint-disable-next-line no-param-reassign
      event.returnValue = '';
    }
    async function navigateAwayGuard(): Promise<boolean> {
      let result = true;
      if (pendingSaveCount.value > 0) {
        result = await prompt({
          title: 'Save Items',
          text: 'There is unsaved data, would you like to continue or cancel and save?',
          positiveButton: 'Discard and Leave',
          negativeButton: 'Don\'t Leave',
          confirm: true,
        });
      }
      return result;
    }

    const globalHandler = {
      ...handler,
      save,
      setCheckedTypes: updateCheckedTypes,
      trackSplit,
      trackEnable: updateCheckedTrackId,
      updateTypeName,
      updateTypeStyle,
      removeTypeTracks,
      deleteType,
      setAttribute,
      deleteAttribute,
    };

    provideAnnotator(
      {
        attributes,
        allTypes,
        datasetId: currentId,
        usedTypes,
        checkedTrackIds,
        checkedTypes,
        editingMode,
        enabledTracks,
        frame,
        intervalTree,
        mergeList,
        pendingSaveCount,
        trackMap,
        filteredTracks,
        typeStyling,
        selectedKey,
        selectedTrackId,
        stateStyles: stateStyling,
        visibleModes,
      },
      globalHandler,
    );

    /** Trigger data load */
    const loadData = async (id = props.id) => {
      currentId.value = id;
      return (
        Promise.all([
          loadMetadata(currentId.value).then((meta) => {
            populateTypeStyles(meta.customTypeStyling);
            if (meta.customTypeStyling) {
              importTypes(Object.keys(meta.customTypeStyling), false);
            }
            if (meta.attributes) {
              loadAttributes(meta.attributes);
            }
            populateConfidenceFilters(meta.confidenceFilters);
            datasetName.value = meta.name;
            frameRate.value = meta.fps;
            imageData.value = cloneDeep(meta.imageData) as FrameImage[];
            videoUrl.value = meta.videoUrl;
            datasetType.value = meta.type as DatasetType;
            // TODO: Data is ready for MultiView, just setting it to default display for now
            const defaultCameraMeta = meta.multiCamMedia?.cameras[meta.multiCamMedia.display];
            const cameras = meta.multiCamMedia?.cameras;
            if (defaultCameraMeta && cameras && meta.multiCamMedia) {
              defaultCamera.value = meta.multiCamMedia.display;
              multiCamList.value = Object.keys(cameras).concat(['MultiCam Base']);
              imageData.value = cloneDeep(defaultCameraMeta.imageData) as FrameImage[];
              videoUrl.value = defaultCameraMeta.videoUrl;
              datasetType.value = defaultCameraMeta.type;
              currentId.value = `${props.id}/${defaultCamera.value}`;
            }
            loadDetections(currentId.value).then((tracks) => {
              Object.values(tracks).forEach(
                (trackData) => insertTrack(Track.fromJSON(trackData), { imported: true }),
              );
            });
          }),
        ]).then(() => {
          loaded.value = true;
        }).catch((err) => {
          loaded.value = false;
          // Cleaner displaying of interal errors for desktop
          if (err.response?.data && err.response?.status === 500 && !err.response?.data?.message) {
            const fullText = err.response.data;
            const start = fullText.indexOf('Error:');
            const html = (fullText.substr(start, fullText.indexOf('<br>') - start));
            const errorEl = document.createElement('div');
            errorEl.innerHTML = html;
            loadError.value = errorEl.innerText
              .concat(". If you don't know how to resolve this, please contact the server administrator.");
            throw err;
          }
          loadError.value = (err.response?.data?.message || err).toString()
            .concat(" If you don't know how to resolve this, please contact the server administrator.");
          throw err;
        })
      );
    };
    loadData();
    const reloadData = async () => {
      clearAllTracks();
      loaded.value = false;
      await loadData();
    };

    const changeCamera = async (camera: string) => {
      if (camera !== 'MultiCam Base') {
        currentId.value = `${props.id}/${camera}`;
      } else {
        currentId.value = props.id;
      }
      clearAllTracks();
      loaded.value = false;
      ctx.emit('updateId', currentId.value);
      await loadData(currentId.value);
    };
    return {
      reloadData,
      multiCamList,
      defaultCamera,
      changeCamera,
      /* props */
      confidenceThreshold,
      datasetName,
      datasetType,
      editingTrack,
      editingMode,
      eventChartData,
      frame,
      frameRate,
      imageData,
      lineChartData,
      loaded,
      loadError,
      mediaController,
      mergeMode: mergeInProgress,
      newTrackSettings: clientSettings.newTrackSettings,
      typeSettings: clientSettings.typeSettings,
      pendingSaveCount,
      playbackComponent,
      recipes,
      selectedFeatureHandle,
      selectedTrackId,
      selectedKey,
      videoUrl,
      visibleModes,
      /* methods */
      handler: globalHandler,
      save,
      saveThreshold,
      updateNewTrackSettings,
      updateTypeSettings,
      updateTypeStyle,
      updateTypeName,
      removeTypeTracks,
      importTypes,
      // For Navigation Guarding
      navigateAwayGuard,
      warnBrowserExit,
    };
  },
});
</script>

<template>
  <v-main class="viewer">
    <v-app-bar app>
      <slot name="title" />
      <span
        class="title pl-3"
      >
        {{ datasetName }}
      </span>
      <div
        v-if="multiCamList.length"
        class="px-2 mt-6"
      >
        <v-select
          :value="defaultCamera"
          :items="multiCamList"
          label="Camera"
          @change="changeCamera"
        />
      </div>
      <v-spacer />
      <template #extension>
        <span>Viewer/Edit Controls</span>
        <editor-menu
          v-bind="{ editingMode, visibleModes, editingTrack, recipes, mergeMode }"
          class="shrink px-6"
          @set-annotation-state="handler.setAnnotationState"
        />
        <delete-controls
          v-bind="{ editingMode, selectedFeatureHandle }"
          @delete-point="handler.removePoint"
          @delete-annotation="handler.removeAnnotation"
        />
        <v-spacer />
        <slot name="extension-right" />
      </template>
      <slot name="title-right" />
      <user-guide-button annotating />
      <v-badge
        overlap
        bottom
        :content="pendingSaveCount"
        :value="pendingSaveCount > 0"
        offset-x="14"
        offset-y="18"
      >
        <v-btn
          icon
          :disabled="pendingSaveCount === 0"
          @click="save"
        >
          <v-icon>mdi-content-save</v-icon>
        </v-btn>
      </v-badge>
    </v-app-bar>
    <v-row
      no-gutters
      class="fill-height"
      style="min-width: 700px;"
    >
      <sidebar
        v-bind="{ newTrackSettings, typeSettings }"
        @update-new-track-settings="updateNewTrackSettings($event)"
        @update-type-settings="updateTypeSettings($event)"
        @import-types="importTypes($event)"
        @track-seek="mediaController.seek($event)"
      >
        <ConfidenceFilter
          :confidence.sync="confidenceThreshold"
          @end="saveThreshold"
        />
      </sidebar>
      <v-col style="position: relative">
        <component
          :is="datasetType === 'image-sequence' ? 'image-annotator' : 'video-annotator'"
          v-if="(imageData.length || videoUrl) && loaded"
          ref="playbackComponent"
          v-mousetrap="[
            { bind: 'n', handler: () => handler.trackAdd() },
            { bind: 'r', handler: () => mediaController.resetZoom() },
            { bind: 'esc', handler: () => handler.trackAbort() },
          ]"
          v-bind="{ imageData, videoUrl, frameRate }"
          class="playback-component"
          @frame-update="frame = $event"
        >
          <template slot="control">
            <controls-container
              v-bind="{ lineChartData, eventChartData, datasetType }"
              @select-track="handler.trackSelect"
            />
          </template>
          <layer-manager />
        </component>
        <div
          v-else
          class="d-flex justify-center align-center fill-height"
        >
          <v-alert
            v-if="loadError"
            type="error"
            prominent
            max-width="60%"
          >
            <p class="ma-2">
              {{ loadError }}
            </p>
          </v-alert>
          <v-progress-circular
            v-else
            indeterminate
            size="100"
            width="15"
            color="light-blue"
          >
            Loading
          </v-progress-circular>
        </div>
      </v-col>
    </v-row>
  </v-main>
</template>
