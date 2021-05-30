<script lang="ts">
import { shell } from 'electron';
import moment, { utc } from 'moment';
import { defineComponent, ref, onBeforeUnmount } from '@vue/composition-api';

import { DesktopJob } from 'platform/desktop/constants';

import BrowserLink from './BrowserLink.vue';
import NavigationBar from './NavigationBar.vue';
import { datasets } from '../store/dataset';
import { recentHistory } from '../store/jobs';

export default defineComponent({
  components: {
    BrowserLink,
    NavigationBar,
  },
  setup() {
    const visibleOutput = ref(null as string | null);

    /* clockDriver causes the page to re-render every second */
    const clockDriver = ref(0);
    const clockDriverInterval = setInterval(() => {
      clockDriver.value += 1;
    }, 1000);
    onBeforeUnmount(() => clearInterval(clockDriverInterval));

    const truncateOutputAtLines = 500;

    function toggleVisibleOutput(job: DesktopJob) {
      if (job.key === visibleOutput.value) {
        visibleOutput.value = null;
      } else {
        visibleOutput.value = job.key;
      }
    }

    async function openPath(job: DesktopJob) {
      shell.openPath(job.workingDir);
    }

    return {
      clockDriver,
      datasets,
      recentHistory,
      moment,
      utc,
      visibleOutput,
      truncateOutputAtLines,
      /* methods */
      openPath,
      toggleVisibleOutput,
    };
  },
});
</script>

<template>
  <v-main>
    <navigation-bar />
    <v-container>
      <v-col>
        <v-row>
          <span style="display: none;">{{ clockDriver }}</span>
          <v-col>
            <h1 class="text-h4 mb-4 font-weight-light">
              Job History ({{ recentHistory.length }})
            </h1>
            <v-card
              v-for="job in recentHistory.slice().reverse()"
              :key="job.job.key"
              class=" mb-4"
              min-width="100%"
            >
              <v-progress-linear
                :color="job.job.exitCode === 0 ? 'success' : 'primary'"
                :indeterminate="job.job.exitCode === null"
                :value="100"
              />
              <v-row
                no-gutters
                class="pt-3"
              >
                <v-col cols="1">
                  <div class="mt-2 d-flex flex-row justify-center">
                    <v-icon
                      v-if="job.job.exitCode === null"
                    >
                      mdi-spin mdi-sync
                    </v-icon>
                    <v-icon
                      v-else-if="job.job.exitCode === 0"
                      color="success"
                    >
                      mdi-check-circle
                    </v-icon>
                    <v-icon
                      v-else
                      color="error"
                    >
                      mdi-close
                    </v-icon>
                  </div>
                </v-col>
                <v-col cols="8">
                  <v-card-title class="primary--text text--lighten-3 text-decoration-none pt-0">
                    {{ job.job.jobType }}: {{ datasets[job.job.datasetIds[0].split('/')[0]].name }}
                  </v-card-title>
                  <v-card-subtitle>
                    <table class="key-value-table">
                      <tr v-if="'pipeline' in job.job.args">
                        <td>Pipe</td>
                        <td>{{ job.job.args.pipeline.pipe }}</td>
                      </tr>
                      <tr>
                        <td>PID</td>
                        <td>{{ job.job.pid }}</td>
                      </tr>
                      <tr>
                        <td>datasets</td>
                        <td>
                          {{ job.job.datasetIds.join(', ') }}
                        </td>
                      </tr>
                      <tr>
                        <td>work dir</td>
                        <td>
                          <span
                            class="selectable"
                            @click="openPath(job.job)"
                          >
                            <span class="text-decoration-underline">show in file manager</span>
                            <v-icon
                              small
                              class="mx-2"
                            >
                              mdi-folder-open
                            </v-icon>
                          </span>
                        </td>
                      </tr>
                    </table>
                  </v-card-subtitle>
                </v-col>
                <v-col cols="3">
                  <div class="ma-3">
                    <v-icon class="pr-2">
                      mdi-calendar
                    </v-icon>
                    {{ moment(job.job.startTime).fromNow() }}
                  </div>
                  <div
                    class="ma-3 pr-2"
                  >
                    <v-icon class="pr-2">
                      mdi-timer
                    </v-icon>
                    <span>
                      {{
                        utc(
                          moment(job.job.endTime || moment())
                            .diff(moment(job.job.startTime))
                        )
                          .format("HH:mm:ss")
                      }}
                    </span>
                  </div>
                  <v-btn
                    text
                    small
                    class="mb-2 primary--text text--lighten-3 text-decoration-none"
                    @click="toggleVisibleOutput(job.job)"
                  >
                    <v-icon
                      color="primary lighten-3"
                      class="pr-2"
                    >
                      mdi-console
                    </v-icon> {{ job.job.key === visibleOutput ? 'Hide' : 'Show' }} Console Log
                  </v-btn>
                </v-col>
              </v-row>
              <v-row
                v-if="visibleOutput === job.job.key"
                class="pa-3"
                no-gutters
              >
                <v-card
                  flat
                  rounded
                  color="black"
                  min-width="100%"
                  height="220"
                  class="px-4 py-1"
                  style="overflow-y: auto;"
                >
                  <p
                    v-for="(line, i) in job.logs.slice(-1 * truncateOutputAtLines, -1).reverse()"
                    :key="line + i"
                    class="my-1 terminal"
                  >
                    {{ job.logs.length - i - 1 }}. {{ line.replace('\n', '') }}
                  </p>
                  <p
                    v-if="job.logs.length > truncateOutputAtLines"
                    class="my-1 terminal terminal-meta"
                  >
                    ______________________________
                    <br><br>
                    Logging truncated at {{ truncateOutputAtLines }} most recent lines.
                    See job working directory for full console log.
                    <br>
                    {{ job.job.workingDir }}
                  </p>
                </v-card>
              </v-row>
            </v-card>
          </v-col>
        </v-row>
      </v-col>
    </v-container>
  </v-main>
</template>

<style lang="scss" scoped>
@import 'dive-common/components/styles/KeyValueTable.scss';

.terminal {
  font-family: monospace;
  font-size: 12px;

  &.terminal-meta {
    opacity: 0.7;
  }
}

.selectable {
  cursor: pointer;

  &:hover {
    opacity: 0.8;
  }
}
</style>
