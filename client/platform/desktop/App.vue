<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script lang="ts">
import { defineComponent } from '@vue/composition-api';
import { provideApi } from 'dive-common/apispec';
import statefulApi from './frontend/store';

export default defineComponent({
  name: 'App',
  components: {},
  setup() {
    provideApi(statefulApi());
  },
});
</script>

<style lang="scss">
html {
  overflow-y: auto;
}

.text-xs-center {
  text-align: center !important;
}
</style>
