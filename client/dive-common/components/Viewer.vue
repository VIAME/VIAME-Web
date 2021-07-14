<script lang="ts">
import {
  defineComponent, ref, toRef, computed, Ref, reactive,
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
import { usePrompt } from 'dive-common/vue-utilities/prompt-service';
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
  setup(props) {
    const { prompt } = usePrompt();
    const loadError = ref('');
    const playbackComponent = ref(undefined as Vue | undefined);
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
    const originalFps = ref(null as number | null);
    const imageData = ref([] as FrameImage[]);
    const datasetType: Ref<DatasetType> = ref('image-sequence');
    const datasetName = ref('');
    const saveInProgress = ref(false);
    const videoUrl = ref(undefined as undefined | string);
    const frame = ref(0); // the currently displayed frame number
    const { loadDetections, loadMetadata, saveMetadata } = useApi();
    const progress = reactive({
      // Loaded flag prevents annotator window from populating
      // with stale data from props, for example if a persistent store
      // like vuex is used to drive them.
      loaded: false,
      // Tracks loaded
      progress: 0,
      // Total tracks
      total: 0,
    });

    const progressValue = computed(() => {
      if (progress.total > 0 && (progress.progress !== progress.total)) {
        return Math.round((progress.progress / progress.total) * 100);
      }
      return 0;
    });

    const {
      save: saveToServer,
      markChangesPending,
      pendingSaveCount,
    } = useSave(toRef(props, 'id'));

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
      saveInProgress.value = true;
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
        saveInProgress.value = false;
        throw err;
      }
      saveInProgress.value = false;
    }

    function saveThreshold() {
      saveMetadata(props.id, {
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

    /** Trigger data load */
    const loadData = () => (
      Promise.all([
        loadMetadata(props.id).then((meta) => {
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
          originalFps.value = meta.originalFps;
          imageData.value = cloneDeep(meta.imageData) as FrameImage[];
          videoUrl.value = meta.videoUrl;
          datasetType.value = meta.type as DatasetType;
        }),
        loadDetections(props.id).then(async (trackData) => {
          const tracks = Object.values(trackData);
          progress.total = tracks.length;
          for (let i = 0; i < tracks.length; i += 1) {
            if (i % 4000 === 0) {
            /* Every N tracks, yeild some cycles for other scheduled tasks */
              progress.progress = i;
              // eslint-disable-next-line no-await-in-loop
              await new Promise((resolve) => window.setTimeout(resolve, 500));
            }
            insertTrack(Track.fromJSON(tracks[i]), { imported: true });
          }
        }),
      ]).then(() => {
        progress.loaded = true;
      }).catch((err) => {
        progress.loaded = false;
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
      }));
    loadData();

    const reloadAnnotations = async () => {
      clearAllTracks();
      progress.loaded = false;
      await loadData();
    };

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
      reloadAnnotations,
    };

    provideAnnotator(
      {
        attributes,
        allTypes,
        datasetId: ref(props.id),
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

    return {
      /* props */
      confidenceThreshold,
      datasetName,
      datasetType,
      editingTrack,
      editingMode,
      eventChartData,
      frame,
      frameRate,
      originalFps,
      imageData,
      lineChartData,
      loadError,
      mediaController,
      mergeMode: mergeInProgress,
      newTrackSettings: clientSettings.newTrackSettings,
      typeSettings: clientSettings.typeSettings,
      pendingSaveCount,
      progress,
      progressValue,
      saveInProgress,
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
          :disabled="pendingSaveCount === 0 || saveInProgress"
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
          v-if="(imageData.length || videoUrl) && progress.loaded"
          ref="playbackComponent"
          v-mousetrap="[
            { bind: 'n', handler: () => handler.trackAdd() },
            { bind: 'r', handler: () => mediaController.resetZoom() },
            { bind: 'esc', handler: () => handler.trackAbort() },
          ]"
          v-bind="{ imageData, videoUrl, frameRate, originalFps }"
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
            :indeterminate="progressValue === 0"
            :value="progressValue"
            size="100"
            width="15"
            color="light-blue"
            class="main-progress-linear"
            rotate="-90"
          >
            <span v-if="progressValue === 0">Loading</span>
            <span v-else>{{ progressValue }}%</span>
          </v-progress-circular>
        </div>
      </v-col>
    </v-row>
  </v-main>
</template>
