<script lang="ts">
import {
  computed, defineComponent, Ref, ref, PropType,
} from '@vue/composition-api';
import { GirderFileManager } from '@girder/components/src';
import { withRestError } from 'platform/web-girder/utils';
import { GirderDatasetModel } from 'platform/web-girder/constants';
import { clone } from '../api/viame.service';
import { useGirderRest } from '../plugins/girder';

export default defineComponent({
  components: { GirderFileManager },

  props: {
    source: {
      type: Object as PropType<GirderDatasetModel | null>,
      default: null,
    },
    buttonOptions: {
      type: Object,
      default: () => ({}),
    },
  },

  setup(props, { root }) {
    const girderRest = useGirderRest();
    const open = ref(false);
    // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
    // @ts-ignore
    const location: Ref<GirderDatasetModel> = ref({
      _modelType: 'user',
      // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
      // @ts-ignore
      _id: girderRest.user._id,
      meta: {},
    });
    const newName = ref('');

    const locationIsFolder = computed(() => (location.value._modelType === 'folder'));

    async function click() {
      if (props.source) {
        newName.value = `Clone of ${props.source.name}`;
        open.value = true;
      }
    }

    function setLocation(newLoc: GirderDatasetModel) {
      if (!newLoc.meta?.annotate) {
        location.value = newLoc;
      }
    }

    const { func: doClone, error: cloneError } = withRestError(async () => {
      if (!props.source) {
        throw new Error('No source dataset!');
      }
      const newDataset = await clone({
        folderId: props.source._id,
        name: newName.value,
        parentFolderId: location.value._id,
      });
      root.$router.push({ name: 'viewer', params: { id: newDataset._id } });
    });

    return {
      cloneError,
      location,
      locationIsFolder,
      newName,
      open,
      /* methods */
      click,
      doClone,
      setLocation,
    };
  },
});
</script>

<template>
  <v-dialog
    v-model="open"
    :max-width="800"
    :overlay-opacity="0.95"
  >
    <template #activator="{ attrs, on }">
      <v-tooltip
        v-bind="attrs"
        bottom
        open-delay="400"
        v-on="on"
      >
        <template #activator="{ on: ton, attrs: tattrs }">
          <v-btn
            v-bind="{ ...tattrs, ...buttonOptions }"
            :disabled="source === null || !source.meta.annotate || !!source.meta.subType"
            v-on="{ ...ton, click }"
          >
            <v-icon>
              mdi-content-copy
            </v-icon>
            <span
              v-show="!$vuetify.breakpoint.mdAndDown || buttonOptions.block"
              class="pl-1"
            >
              Clone
            </span>
            <v-spacer />
            <v-icon>mdi-dock-window</v-icon>
          </v-btn>
        </template>
        <span>Create a clone of this data</span>
      </v-tooltip>
    </template>

    <v-card v-if="source">
      <template v-if="source.meta.foreign_media_id">
        <v-card-title>
          This dataset is a clone
        </v-card-title>
        <v-card-text>
          This dataset was cloned from another.  It can be annotated and used
          for pipelines and training like a regular dataset, but its images
          or video are references to an external dataset.
          <router-link :to="{ name: 'viewer', params: { id: source.meta.foreign_media_id } }">
            Open media source dataset.
          </router-link>
        </v-card-text>
      </template>
      <v-divider />
      <v-card-title>
        Create a new clone
      </v-card-title>
      <v-card-text>
        <v-alert
          v-if="cloneError"
          type="error"
          dismissible
        >
          {{ cloneError }}
        </v-alert>
        Create a copy of this dataset in your personal workspace.  You will be able
        to edit annotations and run pipelines on the clone.  This operation does not
        copy, but instead directly references the source media.
        <v-text-field
          v-model="newName"
          label="New clone name"
          class="mt-4"
          outlined
          dense
          block
        />
        <v-card
          outlined
          flat
        >
          <GirderFileManager
            new-folder-enabled
            root-location-disabled
            no-access-control
            :location="location"
            @update:location="setLocation"
          >
            <template #row-widget="{item}">
              <v-chip
                v-if="(item.meta && item.meta.annotate)"
                color="white"
                x-small
                outlined
                class="mx-3"
              >
                dataset
              </v-chip>
            </template>
          </GirderFileManager>
        </v-card>
        <v-btn
          depressed
          block
          color="primary"
          class="mt-4"
          :disabled="!locationIsFolder"
          @click="doClone"
        >
          <span v-if="!locationIsFolder">
            Choose a destination folder...
          </span>
          <span v-else>Clone into {{ location.name }}</span>
        </v-btn>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
