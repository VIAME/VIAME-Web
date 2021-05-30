<template>
  <v-card class="data-details">
    <v-toolbar
      flat="flat"
      dark="dark"
      dense="dense"
      color="primary"
    >
      <v-toolbar-title class="subtitle-1">
        <v-icon class="pr-2 mdi-18px">
          {{ icon }}
        </v-icon>{{ title }}
      </v-toolbar-title>
    </v-toolbar>
    <girder-detail-list
      :rows="info"
      title="Info"
    />
    <slot
      name="actions"
      v-bind="{ subTypeList }"
    />
  </v-card>
</template>

<script>
import Vue from 'vue';
import {
  GirderDetailList,
  mixins,
} from '@girder/components/src';

const {
  dateFormatter,
  sizeFormatter,
  usernameFormatter,
} = mixins;

/**
 * @type {Array<{
 *  value: String,
 *  name: String,
 *  transform: Function
 * }>}
 */
export const DefaultInfoKeys = [
  {
    value: 'size',
    name: 'Contents: ',
    transform: sizeFormatter.methods.formatSize,
  },
  {
    value: 'created',
    name: 'Created on ',
    transform: dateFormatter.methods.formatDate,
  },
  {
    value: 'public',
    name: 'Public: ',
  },
  {
    meta: true,
    value: 'fps',
    name: 'FPS: ',
  },
  {
    meta: true,
    value: 'type',
    name: 'Type: ',
  },
  {
    meta: true,
    value: 'subType',
    name: 'Sub Type: ',
  },
  {
    meta: true,
    value: 'published',
    name: 'Published: ',
  },
];

export default Vue.extend({
  components: {
    GirderDetailList,
  },
  mixins: [sizeFormatter, usernameFormatter],
  props: {
    value: {
      required: true,
      type: Array,
    },
    infoKeys: {
      type: Array,
      default: () => DefaultInfoKeys,
    },
  },
  data() {
    return {
      showUpsert: false,
    };
  },
  inject: ['girderRest'],
  asyncComputed: {
    async details() {
      if (this.datum && this.datum.created) {
        return this.datum;
      } if (this.datum && this.datum._id && this.datum._modelType) {
        const { data } = await this.girderRest.get(`${this.datum._modelType}/${this.datum._id}`);
        return data;
      }
      return null;
    },
  },
  computed: {
    title() {
      if (this.details) {
        return this.details.name || this.formatUsername(this.details);
      }
      if (this.datum) {
        if (this.datum._modelType) {
          return this.datum._modelType;
        }
        if (this.datum.type) {
          return this.datum.type;
        }
      }
      return `${this.value.length} Selection(s)`;
    },
    datum() {
      return this.value.length === 1 ? this.value[0] : undefined;
    },
    icon() {
      return this.datum
        ? this.$vuetify.icons.values[this.datum._modelType]
        : this.$vuetify.icons.values.fileMultiple;
    },
    info() {
      if (this.details) {
        /* If this is a single datum */
        return this.infoKeys
          .map((k) => {
            let val = k.meta
              ? this.details.meta?.[k.value]
              : this.details[k.value];
            if (!val) {
              return null;
            }
            if (k.transform) {
              val = k.transform(val);
            }
            return `${k.name}${val}`;
          })
          .filter((v) => v);
      } if (this.value.length > 1) {
        /* If this is a multi-selection */
        const reducer = (acc, curr) => {
          acc[curr._modelType] += 1;
          acc.size += curr.size;
          return acc;
        };
        const typeCounts = this.value.reduce(reducer, {
          item: 0,
          folder: 0,
          size: 0,
        });
        const countMessages = ['item', 'folder']
          .filter((k) => typeCounts[k] > 0)
          .map((k) => `${typeCounts[k]} ${k}(s) selected`);
        const sizeMessage = `Total size: ${this.formatSize(typeCounts.size)}`;
        return [...countMessages, sizeMessage];
      }
      return [];
    },
    // Used to pass to Taining/Cloning/Pipelines for filtering stereo/multicam features
    subTypeList() {
      if (this.details) {
        if (this.details.meta?.subType) {
          return [this.details.meta.subType];
        }
      } else if (this.value.length > 1) {
        return this.value.map((item) => {
          if (item.meta && item.meta.subType) {
            return item.meta.subType;
          }
          return '';
        });
      }
      return [''];
    },
  },
});
</script>
