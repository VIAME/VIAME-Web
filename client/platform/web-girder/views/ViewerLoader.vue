<script lang="ts">
import {
  defineComponent, onBeforeUnmount, onMounted, ref, toRef, computed,
} from '@vue/composition-api';

import { importAnnotation } from 'platform/web-girder/api/viame.service';

import Viewer from 'dive-common/components/Viewer.vue';
import NavigationTitle from 'dive-common/components/NavigationTitle.vue';
import RunPipelineMenu from 'dive-common/components/RunPipelineMenu.vue';
import ImportAnnotations from 'dive-common/components/ImportAnnotations.vue';

import JobsTab from './JobsTab.vue';
import { getPathFromLocation } from '../utils';
import Export from './Export.vue';
import Clone from './Clone.vue';

const buttonOptions = {
  text: true,
  color: 'grey lighten-1',
  outlined: true,
  depressed: true,
  class: ['mx-1'],
};

const menuOptions = {
  offsetY: true,
  bottom: true,
};

/**
 * ViewerLoader is responsible for loading
 * data from girder.
 */
export default defineComponent({
  components: {
    Clone,
    Export,
    JobsTab,
    RunPipelineMenu,
    NavigationTitle,
    Viewer,
    ImportAnnotations,
  },

  props: {
    id: {
      type: String,
      required: true,
    },
  },

  // TODO: This will require an import from vue-router for Vue3 compatibility
  async beforeRouteLeave(to, from, next) {
    if (await this.viewerRef.navigateAwayGuard()) {
      next();
    }
  },

  setup(props, { root }) {
    const viewerRef = ref();
    const brandData = toRef(root.$store.state.Brand, 'brandData');
    const location = toRef(root.$store.state.Location, 'location');
    const dataPath = computed(() => getPathFromLocation(location.value));
    onMounted(() => {
      window.addEventListener('beforeunload', viewerRef.value.warnBrowserExit);
    });
    onBeforeUnmount(() => {
      window.removeEventListener('beforeunload', viewerRef.value.warnBrowserExit);
    });
    const importAnnotationFile = async (id: string, file: File) => {
      const result = await importAnnotation(id, file);
      if (result) {
        viewerRef.value.reloadData();
      }
    };
    return {
      buttonOptions,
      menuOptions,
      viewerRef,
      dataPath,
      brandData,
      importAnnotationFile,
    };
  },
});
</script>

<template>
  <Viewer
    :id="id"
    :key="id"
    ref="viewerRef"
  >
    <template #title>
      <NavigationTitle :name="brandData.name" />
      <v-tabs
        icons-and-text
        hide-slider
        style="flex-basis:0; flex-grow:0;"
      >
        <v-tab :to="dataPath">
          Data
          <v-icon>mdi-database</v-icon>
        </v-tab>
        <JobsTab />
      </v-tabs>
    </template>
    <template #title-right>
      <RunPipelineMenu
        v-bind="{ buttonOptions, menuOptions }"
        :selected-dataset-ids="[id]"
      />
      <Export
        v-bind="{ buttonOptions, menuOptions }"
        :dataset-id="id"
        block-on-unsaved
      />
      <ImportAnnotations
        v-bind="{ buttonOptions, menuOptions }"
        :dataset-id="id"
        block-on-unsaved
        @import-annotation-file="importAnnotationFile"
      />
      <Clone
        v-if="$store.state.Dataset.meta"
        v-bind="{ buttonOptions }"
        :source="$store.state.Dataset.meta"
      />
    </template>
  </Viewer>
</template>
