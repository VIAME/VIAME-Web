<script lang="ts">
import { defineComponent } from '@vue/composition-api';
import { useApi } from 'dive-common/apispec';

export default defineComponent({
  name: 'ImportAnnotations',
  props: {
    datasetId: {
      type: String,
      default: null,
    },
    blockOnUnsaved: {
      type: Boolean,
      default: false,
    },
    buttonOptions: {
      type: Object,
      default: () => ({}),
    },
    menuOptions: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props, { emit }) {
    const { openFromDisk } = useApi();
    const openUpload = async () => {
      const ret = await openFromDisk('annotation');
      if (!ret.canceled) {
        const path = ret.filePaths[0];
        if (ret.fileList?.length) {
          emit('import-annotation-file', props.datasetId, ret.fileList[0]);
        } else {
          emit('import-annotation-file', props.datasetId, path);
        }
      }
    };
    return {
      openUpload,
    };
  },
});
</script>

<template>
  <v-btn
    class="ma-0"
    v-bind="buttonOptions"
    :disabled="!datasetId"
    @click="openUpload"
  >
    <v-icon>
      mdi-application-import
    </v-icon>
    <span
      v-show="!$vuetify.breakpoint.mdAndDown || buttonOptions.block"
      class="pl-1"
    >
      Import
    </span>
  </v-btn>
</template>

<style scoped lang="scss">
</style>
