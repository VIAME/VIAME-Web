import { Module } from 'vuex';
import { getPipelineList } from '@/lib/api/viame.service';

interface Pipe {
    name: string;
    pipe: string;
    type: string;
}
interface Categories {
    description: string;
    pipes: [Pipe];
}

export interface PipelineState {
    pipelines: null | Record<string, Categories>;
}
const pipelineModule: Module<PipelineState, never> = {
  namespaced: true,
  state: {
    pipelines: null,
  },
  mutations: {
    setPipelines(state, pipelines) {
      state.pipelines = pipelines;
    },
  },
  actions: {
    async fetchPipelines({ commit, state }) {
      if (state.pipelines === null) {
        const { data } = await getPipelineList() as {data: PipelineState};
        // Sort list of pipelines in each category by name
        Object.values(data).forEach((category) => {
          category.pipes.sort((a: Pipe, b: Pipe) => {
            const aName = a.name.toLowerCase();
            const bName = b.name.toLowerCase();
            if (aName > bName) {
              return 1;
            }
            if (aName < bName) {
              return -1;
            }
            return 0;
          });
        });
        commit('setPipelines', data);
        return data;
      }
      return state.pipelines;
    },
  },
};

export default pipelineModule;