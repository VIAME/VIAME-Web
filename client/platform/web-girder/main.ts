import { merge } from 'lodash';
import Vue from 'vue';
import VueGtag from 'vue-gtag';
import VueCompositionApi from '@vue/composition-api';
import { init as SentryInit } from '@sentry/browser';
import { Vue as SentryVue } from '@sentry/integrations';
import { vuetifyConfig as girderVuetifyConfig } from '@girder/components/src';

import registerNotifications from 'vue-media-annotator/notificatonBus';
import snackbarService from 'dive-common/vue-utilities/snackbar-service';
import promptService from 'dive-common/vue-utilities/prompt-service';
import vMousetrap from 'dive-common/vue-utilities/v-mousetrap';

import getVuetify from './plugins/vuetify';
import girderRest from './plugins/girder';
import App from './App.vue';
import router from './router';
import store from './store';

Vue.config.productionTip = false;
Vue.use(VueCompositionApi);
Vue.use(vMousetrap);

if (process.env.NODE_ENV === 'production') {
  SentryInit({
    dsn: process.env.VUE_APP_SENTRY_DSN,
    integrations: [
      new SentryVue({ Vue, logErrors: true }),
    ],
    release: process.env.VUE_APP_GIT_HASH,
  });
  Vue.use(VueGtag, {
    config: { id: process.env.VUE_APP_GTAG },
  }, router);
}

Promise.all([
  store.dispatch('Brand/loadBrand'),
  girderRest.fetchUser(),
]).then(() => {
  const vuetify = getVuetify(merge(girderVuetifyConfig, store.state.Brand.brandData?.vuetify));
  Vue.use(snackbarService(vuetify));
  Vue.use(promptService(vuetify));
  new Vue({
    router,
    store,
    vuetify,
    provide: { girderRest, vuetify },
    render: (h) => h(App),
  })
    .$mount('#app')
    .$snackbarAttach()
    .$promptAttach();

  /** Start notification stream if everything else succeeds */
  registerNotifications(girderRest).connect();
});
