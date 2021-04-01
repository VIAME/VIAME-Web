<script lang="ts">
import {
  defineComponent, ref, toRef, computed, Ref,
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
import RunPipelineMenu from 'dive-common/components/RunPipelineMenu.vue';
import DeleteControls from 'dive-common/components/DeleteControls.vue';
import ControlsContainer from 'dive-common/components/ControlsContainer.vue';
import SidebarLeft from 'dive-common/components/SidebarLeft.vue';
import SidebarRight from 'dive-common/components/SidebarRight.vue';

import {
  useModeManager,
  useSave,
  useSettings,
} from 'dive-common/use';
import { useApi, FrameImage, DatasetType } from 'dive-common/apispec';

export default defineComponent({
  components: {
    ControlsContainer,
    DeleteControls,
    SidebarLeft,
    SidebarRight,
    LayerManager,
    VideoAnnotator,
    ImageAnnotator,
    ConfidenceFilter,
    RunPipelineMenu,
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
    const fps = ref(10 as string | number);
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
    const frameRate = computed(() => {
      if (fps.value) {
        if (typeof fps.value === 'string') {
          const parsed = parseInt(fps.value, 10);
          if (Number.isNaN(parsed)) {
            throw new Error(`Cannot parse fps=${fps.value} as integer`);
          }
          return parsed;
        }
        if (typeof fps.value === 'number') {
          return fps.value;
        }
      }
      return 10;
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

    const { lineChartData } = useLineChart({
      enabledTracks, typeStyling, allTypes,
    });

    const { eventChartData } = useEventChart({
      enabledTracks, selectedTrackId, typeStyling,
    });

    const { clientSettings, updateNewTrackSettings, updateTypeSettings } = useSettings(allTypes);

    // Provides wrappers for actions to integrate with settings
    const {
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
        datasetId: ref(props.id),
        usedTypes,
        checkedTrackIds,
        checkedTypes,
        editingMode,
        enabledTracks,
        frame,
        intervalTree,
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
        fps.value = meta.fps;
        imageData.value = meta.imageData;
        videoUrl.value = meta.videoUrl;
        datasetType.value = meta.type;
      }),
      loadDetections(props.id).then((tracks) => {
        Object.values(tracks).forEach(
          (trackData) => insertTrack(Track.fromJSON(trackData)),
        );
      }),
    ]).then(() => {
      loaded.value = true;
    }).catch((err) => {
      loaded.value = false;
      loadError.value = (err.response?.data?.message || err)
        .concat(" If you don't know how to resolve this, please contact the server administrator.");
      throw err;
    });

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
      imageData,
      lineChartData,
      loaded,
      loadError,
      mediaController,
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
      <v-spacer />
      <template #extension>
        <span>Viewer/Edit Controls</span>
        <editor-menu
          v-bind="{ editingMode, visibleModes, editingTrack, recipes }"
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
      <SidebarLeft
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
      </SidebarLeft>
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
              v-bind="{ lineChartData, eventChartData, imageData, datasetType }"
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
      <SidebarRight
        v-bind="{ newTrackSettings, typeSettings }"
      />
    </v-row>
  </v-main>
</template>
