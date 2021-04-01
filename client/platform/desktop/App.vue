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
  scrollbar-face-color: #646464;
  scrollbar-base-color: #646464;
  scrollbar-3dlight-color: #646464;
  scrollbar-highlight-color: #646464;
  scrollbar-track-color: #000;
  scrollbar-arrow-color: #000;
  scrollbar-shadow-color: #646464;
}

::-webkit-scrollbar { width: 8px; height: 3px;}
::-webkit-scrollbar-button {  background-color: #666; height: 0px; }
::-webkit-scrollbar-track {  background-color: #646464;}
::-webkit-scrollbar-track-piece { background-color: #1E1E1E;}
::-webkit-scrollbar-thumb { height: 10px; background-color: #666; border-radius: 3px;}
::-webkit-scrollbar-corner { background-color: #646464;}
::-webkit-resizer { background-color: #666;}

.text-xs-center {
  text-align: center !important;
}
</style>
