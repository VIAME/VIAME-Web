<script lang="ts">
import Vue, { PropType } from 'vue';
import { cloneDeep } from 'lodash';
import { TypeSettings } from 'dive-common/use/useSettings';

export default Vue.extend({
  name: 'TypeSettingsPanel',

  props: {
    allTypes: {
      type: Array as PropType<Array<string>>,
      required: true,
    },
    typeSettings: {
      type: Object as PropType<TypeSettings>,
      required: true,
    },
  },

  data: () => ({
    itemHeight: 45, // in pixels
    help: {
      import: 'Import multiple Types',
      showEmptyTypes: 'View types that are not used currently.',
      lockTypes: 'Only allows the use of defined types.',
    },
    importInstructions: 'Please provide a list of types (separated by a new line) that you would like to import',
    importDialog: false,
    importTypes: '',
  }),
  methods: {
    /** Reduces the number of update functions utilizing Vuex by indicating the target type */
    saveTypeSettings(event: boolean, target: 'showEmptyTypes' | 'lockTypes') {
      const copy: TypeSettings = cloneDeep(this.typeSettings);
      copy[target] = event; // Modify the value
      this.$emit('update-type-settings', copy);
    },
    confirmImport() {
      // Go through the importTypes and create types for importing
      const types = this.importTypes.split('\n').filter((item) => item.length);
      this.$emit('import-types', types);
      this.importDialog = false;
      this.importTypes = '';
    },
  },
});
</script>

<template>
  <div>
    <v-card
      outlined
      class="pa-2 type-settings"
    >
      <div class="settings-header pb-1">
        Type Settings
      </div>
      <v-row>
        <v-col class="py-1">
          <v-btn
            dense
            small
            outlined
            hide-details
            @click="importDialog = true"
          >
            <v-icon small>
              mdi-plus
            </v-icon>
            Types
          </v-btn>
        </v-col>
        <v-col
          cols="2"
          class="py-1"
          align="right"
        >
          <v-tooltip
            open-delay="200"
            bottom
            max-width="200"
          >
            <template #activator="{ on }">
              <v-icon
                small
                v-on="on"
              >
                mdi-help
              </v-icon>
            </template>
            <span>{{ help.import }}</span>
          </v-tooltip>
        </v-col>
      </v-row>
      <v-row>
        <v-col class="py-1">
          <v-switch
            v-model="typeSettings.showEmptyTypes"
            class="my-0 ml-1 pt-0"
            dense
            label="Show Empty"
            hide-details
            @change="saveTypeSettings($event, 'showEmptyTypes')"
          />
        </v-col>
        <v-col
          cols="2"
          class="py-1"
          align="right"
        >
          <v-tooltip
            open-delay="200"
            bottom
            max-width="200"
          >
            <template #activator="{ on }">
              <v-icon
                small
                v-on="on"
              >
                mdi-help
              </v-icon>
            </template>
            <span>{{ help.showEmptyTypes }}</span>
          </v-tooltip>
        </v-col>
      </v-row>
      <v-row>
        <v-col class="py-1">
          <v-switch
            v-model="typeSettings.lockTypes"
            label="Lock Types"
            class="my-0 ml-1 pt-0"
            dense
            hide-details
            @change="saveTypeSettings($event, 'lockTypes')"
          />
        </v-col>
        <v-col
          cols="2"
          class="py-1"
          align="right"
        >
          <v-tooltip
            open-delay="200"
            bottom
          >
            <template #activator="{ on }">
              <v-icon
                small
                v-on="on"
              >
                mdi-help
              </v-icon>
            </template>
            <span>{{ help.lockTypes }}</span>
          </v-tooltip>
        </v-col>
      </v-row>
    </v-card>
    <v-dialog
      v-model="importDialog"
      width="350"
    >
      <div>
        <v-card>
          <v-card-title>
            Types
            <v-spacer />
            <v-btn
              icon
              small
              @click="importDialog = false"
            >
              <v-icon
                small
              >
                mdi-close
              </v-icon>
            </v-btn>
          </v-card-title>
          <v-card-text>
            {{ importInstructions }}
            <v-form>
              <v-row class="align-center">
                <v-col>
                  <v-textarea
                    v-model="importTypes"
                    outlined
                    no-resize
                    rows="10"
                  />
                </v-col>
              </v-row>
            </v-form>
            <v-alert
              text
              color="error"
            >
              Note:  You will have to check 'View Unused' in the settings to see new empty types
            </v-alert>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn
              depressed=""
              text
              @click="importDialog = false"
            >
              Cancel
            </v-btn>
            <v-btn
              color="primary"
              depressed
              @click="confirmImport"
            >
              Add
            </v-btn>
          </v-card-actions>
        </v-card>
      </div>
    </v-dialog>
  </div>
</template>
