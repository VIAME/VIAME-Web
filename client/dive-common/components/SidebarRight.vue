<script lang="ts">
import { defineComponent, ref, PropType } from '@vue/composition-api';

import { useAllTypes } from 'vue-media-annotator/provides';
import { NewTrackSettings, TypeSettings } from 'dive-common/use/useSettings';

import CreationMode from 'dive-common/components/CreationMode.vue';
import SidebarContainer from 'dive-common/components/SidebarContainer.vue';
import TypeSettingsPanel from 'dive-common/components/TypeSettingsPanel.vue';
import TrackDetailsPanel from 'dive-common/components/TrackDetailsPanel.vue';
import UserGuideDialog from 'dive-common/components/UserGuideDialog.vue';

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
    CreationMode,
    SidebarContainer,
    TypeSettingsPanel,
    TrackDetailsPanel,
    UserGuideDialog,
  },

  setup() {
    const tabs = ref('attrs');
    const allTypesRef = useAllTypes();

    return {
      tabs,
      allTypesRef,
    };
  },
});
</script>

<template>
  <SidebarContainer>
    <div style="overflow: hidden;">
      <v-tabs
        v-model="tabs"
        :height="34"
        dark
      >
        <v-tab
          value="attrs"
        >
          <div class="tab">
            Attributes
          </div>
        </v-tab>
        <v-tab
          value="settings"
        >
          <div class="tab">
            Settings
          </div>
        </v-tab>
        <v-tab
          value="settings"
        >
          <div class="tab">
            Guide
          </div>
        </v-tab>
      </v-tabs>
      <v-tabs-items
        v-model="tabs"
        style="overflow-y: auto; max-height: calc(100% - 34px)"
      >
        <v-tab-item key="attrs">
          <div class="ma-2 settings-header">
            Track & Attribute Editor
          </div>
          <TrackDetailsPanel
            :lock-types="typeSettings.lockTypes"
            :hotkeys-disabled="$prompt.visible()"
            @track-seek="$emit('track-seek', $event)"
          />
        </v-tab-item>
        <v-tab-item key="settings">
          <div class="pa-2">
            <div class="settings-header mb-2">
              UI Settings
            </div>
            <TypeSettingsPanel
              :all-types="allTypesRef"
              :type-settings="typeSettings"
              @update-type-settings="$emit('update-type-settings',$event)"
              @import-types="$emit('import-types',$event)"
            />
            <div class="my-2" />
            <CreationMode
              :all-types="allTypesRef"
              :new-track-settings="newTrackSettings"
              @update-new-track-settings="$emit('update-new-track-settings',$event)"
            />
          </div>
        </v-tab-item>
        <v-tab-item key="guide">
          <UserGuideDialog />
        </v-tab-item>
      </v-tabs-items>
    </div>
  </SidebarContainer>
</template>

<style scoped>
.tab {
  font-size: 11px !important;
}
</style>
