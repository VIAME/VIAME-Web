<script lang="ts">
import {
  defineComponent,
  reactive,
  toRefs,
  PropType,
} from '@vue/composition-api';

import { TypeList, TrackList } from 'vue-media-annotator/components';

import SidebarContainer from 'dive-common/components/SidebarContainer.vue';
import { NewTrackSettings, TypeSettings } from 'dive-common/use/useSettings';

export default defineComponent({
  props: {
    newTrackSettings: {
      type: Object as PropType<NewTrackSettings>,
      required: true,
    },
    typeSettings: {
      type: Object as PropType<TypeSettings>,
      required: true,
    },
  },

  components: {
    SidebarContainer,
    TypeList,
    TrackList,
  },

  setup() {
    const data = reactive({
      currentTab: 'tracks' as 'tracks' | 'attributes',
    });

    function swapTabs() {
      if (data.currentTab === 'tracks') {
        data.currentTab = 'attributes';
      } else {
        data.currentTab = 'tracks';
      }
    }

    return {
      swapTabs,
      ...toRefs(data),
    };
  },
});
</script>

<template>
  <SidebarContainer>
    <div class="wrapper d-flex flex-column">
      <TypeList
        :show-empty-types="typeSettings.showEmptyTypes"
        class="flex-shrink-1 flex-grow-1 typelist"
      />
      <slot />
      <v-spacer />
      <v-divider />
      <TrackList
        class="flex-grow-0 flex-shrink-0"
        :new-track-mode="newTrackSettings.mode"
        :new-track-type="newTrackSettings.type"
        :lock-types="typeSettings.lockTypes"
        :hotkeys-disabled="$prompt.visible()"
        @track-seek="$emit('track-seek', $event)"
      />
    </div>
  </SidebarContainer>
</template>

<style scoped>
.wrapper {
  /* height: 100%; */
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
}

.typelist {
  min-height: 250px;
}

.swap-button {
  position: absolute;
  top: 5px;
  right: 16px;
  z-index: 1;
}
</style>
