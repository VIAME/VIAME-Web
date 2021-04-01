<script lang="ts">
import {
  computed,
  defineComponent,
  Ref,
  ref,
} from '@vue/composition-api';

import {
  useSelectedTrackId,
  useFrame,
  useEditingMode,
  useTypeStyling,
  useAllTypes,
  useHandler,
  useTrackMap,
  useAttributes,
} from 'vue-media-annotator/provides';
import { getTrack } from 'vue-media-annotator/use/useTrackStore';
import { Attribute } from 'vue-media-annotator/use/useAttributes';

import AttributeInput from 'dive-common/components/AttributeInput.vue';
import AttributeEditor from 'dive-common/components/AttributeEditor.vue';
import AttributeSubsection from 'dive-common/components/AttributesSubsection.vue';
import ConfidenceSubsection from 'dive-common/components/ConfidenceSubsection.vue';


export default defineComponent({
  components: {
    AttributeInput,
    AttributeEditor,
    AttributeSubsection,
    ConfidenceSubsection,
  },
  props: {
    lockTypes: {
      type: Boolean,
      default: false,
    },
    hotkeysDisabled: {
      type: Boolean,
      required: true,
    },
  },
  setup(props) {
    const attributes = useAttributes();
    const editingAttribute: Ref<Attribute | null> = ref(null);
    const editingError: Ref<string | null> = ref(null);
    const editingModeRef = useEditingMode();
    const typeStylingRef = useTypeStyling();
    const allTypesRef = useAllTypes();
    const trackMap = useTrackMap();
    const { trackSelectNext, trackSplit, removeTrack } = useHandler();

    //Edit/Set single value by clicking
    const editIndividual: Ref<Attribute | null> = ref(null);


    const frameRef = useFrame();
    const selectedTrackIdRef = useSelectedTrackId();
    const { setAttribute, deleteAttribute } = useHandler();
    const selectedTrack = computed(() => {
      if (selectedTrackIdRef.value !== null) {
        return getTrack(trackMap, selectedTrackIdRef.value);
      }
      return null;
    });

    function setEditIndividual(attribute: Attribute | null) {
      editIndividual.value = attribute;
    }
    function resetEditIndividual(event: MouseEvent) {
      // Only reset if not clicking on a v-input object
      if (editIndividual.value) {
        const path = event.composedPath() as HTMLElement[];
        const inputs = ['INPUT', 'SELECT'];
        if (
          path.find(
            (item: HTMLElement) => (item.classList && item.classList.contains('v-input'))
              || inputs.includes(item.nodeName),
          )
        ) {
          return;
        }
        editIndividual.value = null;
      }
    }

    async function closeEditor() {
      editingAttribute.value = null;
      editingError.value = null;
    }

    function addAttribute(type: 'Track' | 'Detection') {
      //TS doesn't understand
      const belongs = type.toLowerCase() as 'track' | 'detection';
      editingAttribute.value = {
        belongs,
        datatype: 'text',
        name: `New${type}Attribute`,
        key: '',
      };
    }
    function editAttribute(attribute: Attribute) {
      editingAttribute.value = attribute;
    }
    async function saveAttributeHandler({ data, oldAttribute }: {
      oldAttribute?: Attribute;
      data: Attribute;
    }) {
      editingError.value = null;
      if (!oldAttribute && attributes.value.some((attribute) => (
        attribute.name === data.name
        && attribute.belongs === data.belongs))) {
        editingError.value = 'Attribute with that name exists';
        return;
      }

      try {
        await setAttribute({ data, oldAttribute });
      } catch (err) {
        editingError.value = err.message;
      }
      if (!editingError.value) {
        closeEditor();
      }
    }
    async function deleteAttributeHandler(data: Attribute) {
      editingError.value = null;
      try {
        await deleteAttribute({ data });
      } catch (err) {
        editingError.value = err.message;
      }
      if (!editingError.value) {
        closeEditor();
      }
    }

    const mouseTrap = computed(() => {
      const disabled = props.hotkeysDisabled;
      return [
        {
          bind: 'up',
          handler: () => {
            trackSelectNext(-1);
          },
          disabled,
        },
        {
          bind: 'down',
          handler: () => {
            trackSelectNext(1);
          },
          disabled,
        },
        {
          bind: 'del',
          handler: () => {
            if (selectedTrackIdRef.value !== null) {
              removeTrack([selectedTrackIdRef.value]);
            }
          },
          disabled,
        },
        {
          bind: 'x',
          handler: () => trackSplit(selectedTrackIdRef.value, frameRef.value),
          disabled,
        },
      ];
    });

    return {
      selectedTrackIdRef,
      /* Attributes */
      attributes,
      /* Editing */
      editingAttribute,
      saveAttributeHandler,
      deleteAttributeHandler,
      editingError,
      editIndividual,
      /* Selected */
      selectedTrack,
      /* Update functions */
      closeEditor,
      editAttribute,
      addAttribute,
      editingModeRef,
      typeStylingRef,
      allTypesRef,
      setEditIndividual,
      resetEditIndividual,
      mouseTrap,
    };
  },
});
</script>

<template>
  <div
    ref="card"
    v-mousetrap="mouseTrap"
    @click.native="resetEditIndividual"
  >
    <div
      v-if="!selectedTrack"
      class="ml-4 body-2"
    >
      No Track selected
    </div>
    <template v-else>
      <datalist id="allTypesOptions">
        <option
          v-for="type in allTypesRef"
          :key="type"
          :value="type"
        >
          {{ type }}
        </option>
      </datalist>
      <confidence-subsection
        style="max-height:33vh"
        :confidence-pairs="selectedTrack.confidencePairs"
      />
      <attribute-subsection
        mode="Track"
        :attributes="attributes"
        :edit-individual="editIndividual"
        @edit-attribute="editAttribute($event)"
        @set-edit-individual="setEditIndividual($event)"
        @add-attribute="addAttribute"
      />
      <attribute-subsection
        mode="Detection"
        :attributes="attributes"
        :edit-individual="editIndividual"
        @edit-attribute="editAttribute($event)"
        @set-edit-individual="setEditIndividual($event)"
        @add-attribute="addAttribute"
      />
    </template>
    <v-dialog
      :value="editingAttribute != null"
      max-width="550"
      @click:outside="closeEditor"
      @keydown.esc.stop="closeEditor"
    >
      <attribute-editor
        v-if="editingAttribute != null"
        :selected-attribute="editingAttribute"
        :error="editingError"
        @close="closeEditor"
        @save="saveAttributeHandler"
        @delete="deleteAttributeHandler"
      />
    </v-dialog>
  </div>
</template>
