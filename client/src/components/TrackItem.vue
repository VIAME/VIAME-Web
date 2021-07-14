<script lang="ts">
import {
  defineComponent, computed, watch, reactive, PropType, toRef, ref,
} from '@vue/composition-api';
import TooltipBtn from './TooltipButton.vue';
import { useFrame, useHandler, useAllTypes } from '../provides';
import Track from '../track';

export default defineComponent({
  name: 'TrackItem',

  components: { TooltipBtn },

  props: {
    solo: {
      type: Boolean,
      default: false,
    },
    trackType: {
      type: String,
      required: true,
    },
    track: {
      type: Object as PropType<Track>,
      required: true,
    },
    inputValue: {
      type: Boolean,
      required: true,
    },
    selected: {
      type: Boolean,
      required: true,
    },
    editing: {
      type: Boolean,
      required: true,
    },
    merging: {
      type: Boolean,
      default: false,
    },
    color: {
      type: String,
      required: true,
    },
    lockTypes: {
      type: Boolean,
      default: false,
    },
  },

  setup(props, { root, emit }) {
    const vuetify = root.$vuetify;
    const frameRef = useFrame();
    const handler = useHandler();
    const allTypesRef = useAllTypes();
    const trackTypeRef = toRef(props, 'trackType');
    const typeInputBoxRef = ref(undefined as undefined | HTMLInputElement);
    const data = reactive({
      trackTypeValue: props.trackType,
      skipOnFocus: false,
      inputError: false,
    });

    /* Use of revision is safe because it will only create a dependency when track is selected */
    const feature = computed(() => {
      if (props.track.revision.value) {
        const { features, interpolate } = props.track.canInterpolate(frameRef.value);
        const [real, lower, upper] = features;
        return {
          real,
          lower,
          upper,
          shouldInterpolate: interpolate,
          targetKeyframe: real?.keyframe ? real : (lower || upper),
          isKeyframe: real?.keyframe,
        };
      }
      return {
        real: null,
        lower: null,
        upper: null,
        targetKeyframe: null,
        shouldInterpolate: false,
        isKeyframe: false,
      };
    });

    /* isTrack distinguishes between track and detection */
    const isTrack = computed(() => props.track.length > 1 || feature.value.shouldInterpolate);

    /* Sets styling for the selected track */
    const style = computed(() => {
      if (props.selected) {
        return {
          'background-color': `${vuetify.theme.themes.dark.accentBackground}`,
        };
      }
      return {};
    });

    /* Update internal model if external prop changes */
    watch(trackTypeRef, (val) => { data.trackTypeValue = val; });

    function focusType() {
      if (props.selected && typeInputBoxRef.value !== undefined) {
        data.skipOnFocus = true;
        typeInputBoxRef.value.focus();
        if (!props.lockTypes) {
          typeInputBoxRef.value.select();
        }
      }
    }

    function blurType(e: KeyboardEvent) {
      (e.target as HTMLInputElement).blur();
    }

    function onBlur(e: KeyboardEvent) {
      if (data.trackTypeValue.trim() === '') {
        data.trackTypeValue = props.trackType;
      } else if (data.trackTypeValue !== props.trackType) {
        /* horrendous hack to prevent race. https://github.com/Kitware/dive/issues/475 */
        window.setTimeout(() => {
          handler.trackTypeChange(props.track.trackId, data.trackTypeValue);
        }, 100);
      }
      if (props.lockTypes) {
        blurType(e);
      }
    }

    function onFocus() {
      if (!data.skipOnFocus) {
        data.trackTypeValue = '';
      }
      data.skipOnFocus = false;
    }

    const keyframeDisabled = computed(() => (
      !feature.value.real && !feature.value.shouldInterpolate)
      || (props.track.length === 1 && frameRef.value === props.track.begin));

    function toggleKeyframe() {
      if (!keyframeDisabled.value) {
        props.track.toggleKeyframe(frameRef.value);
      }
    }

    function toggleInterpolation() {
      props.track.toggleInterpolation(frameRef.value);
    }

    function gotoNext() {
      const nextFrame = props.track.getNextKeyframe(frameRef.value + 1);
      if (nextFrame !== undefined) {
        emit('seek', nextFrame);
      }
    }

    function gotoPrevious() {
      const previousFrame = props.track.getPreviousKeyframe(frameRef.value - 1);
      if (previousFrame !== undefined) {
        emit('seek', previousFrame);
      }
    }

    function onInputKeyEvent(e: KeyboardEvent) {
      switch (e.code) {
        case 'Escape':
        case 'Enter':
          blurType(e);
          break;
        case 'ArrowDown':
          data.trackTypeValue = '';
          break;
        default:
          break;
      }
    }

    return {
      /* data */
      data,
      feature,
      isTrack,
      style,
      typeInputBoxRef,
      frame: frameRef,
      allTypes: allTypesRef,
      keyframeDisabled,
      /* methods */
      blurType,
      focusType,
      gotoNext,
      gotoPrevious,
      handler,
      onBlur,
      onFocus,
      onInputKeyEvent,
      toggleInterpolation,
      toggleKeyframe,
    };
  },
});
</script>

<template>
  <div
    class="track-item d-flex flex-column align-start hover-show-parent px-1"
    :style="style"
  >
    <v-row
      class="pt-2 justify-center item-row"
      no-gutters
    >
      <div
        v-if="solo"
        class="type-color-box"
        :style="{
          backgroundColor: color,
        }"
      />
      <v-checkbox
        v-else
        class="my-0 ml-1 pt-0"
        dense
        hide-details
        :input-value="inputValue"
        :color="color"
        @change="handler.trackEnable(track.trackId, $event)"
      />
      <v-tooltip
        open-delay="200"
        bottom
        max-width="200"
        :disabled="track.trackId.toString().length < 8"
      >
        <template #activator="{ on }">
          <div
            class="trackNumber pl-0 pr-2"
            v-on="on"
            @click.self="handler.trackSeek(track.trackId)"
          >
            {{ track.trackId }}
          </div>
        </template>
        <span> {{ track.trackId }} </span>
      </v-tooltip>
      <v-spacer />
      <select
        v-if="lockTypes"
        ref="typeInputBoxRef"
        v-model="data.trackTypeValue"
        class="input-box select-input"
        @focus="onFocus"
        @change="onBlur"
        @keydown="onInputKeyEvent"
      >
        <option
          v-for="item in allTypes"
          :key="item"
          :value="item"
        >
          {{ item }}
        </option>
      </select>
      <input
        v-else
        ref="typeInputBoxRef"
        v-model="data.trackTypeValue"
        type="text"
        list="allTypesOptions"
        class="input-box"
        @focus="onFocus"
        @blur="onBlur"
        @keydown="onInputKeyEvent"
      >
      <v-icon
        v-if="lockTypes"
        small
      >
        mdi-lock
      </v-icon>
    </v-row>
    <v-row
      class="my-1 justify-center item-row flex-nowrap"
      no-gutters
    >
      <v-spacer v-if="!isTrack" />
      <template v-if="selected">
        <span
          v-show="false"
          v-mousetrap="[
            { bind: 'shift+enter', handler: focusType },
            { bind: 'k', handler:toggleKeyframe},
            { bind: 'i', handler:toggleInterpolation},
            { bind: 'home', handler: () => $emit('seek', track.begin)},
            { bind: 'end', handler: () => $emit('seek', track.end)},
          ]"
        />
        <tooltip-btn
          color="error"
          icon="mdi-delete"
          :disabled="merging"
          :tooltip-text="`Delete ${isTrack ? 'Track' : 'Detection'}`"
          @click="handler.removeTrack([track.trackId])"
        />

        <tooltip-btn
          v-if="isTrack"
          :disabled="!track.canSplit(frame) || merging"
          icon="mdi-call-split"
          tooltip-text="Split Track"
          @click="handler.trackSplit(track.trackId, frame)"
        />

        <tooltip-btn
          v-if="isTrack"
          :icon="(feature.isKeyframe)
            ? 'mdi-star'
            : 'mdi-star-outline'"
          :disabled="keyframeDisabled"
          tooltip-text="Toggle keyframe"
          @click="toggleKeyframe"
        />

        <tooltip-btn
          v-if="isTrack"
          :icon="(feature.shouldInterpolate)
            ? 'mdi-vector-selection'
            : 'mdi-selection-off'"
          tooltip-text="Toggle interpolation"
          @click="toggleInterpolation"
        />
      </template>
      <v-spacer v-if="isTrack" />
      <template v-if="isTrack">
        <tooltip-btn
          icon="mdi-chevron-double-left"
          tooltip-text="Seek to track beginning"
          @click="$emit('seek', track.begin)"
        />

        <tooltip-btn
          icon="mdi-chevron-left"
          tooltip-text="Seek to previous keyframe"
          @click="gotoPrevious"
        />

        <tooltip-btn
          icon="mdi-chevron-right"
          tooltip-text="Seek to next keyframe"
          @click="gotoNext"
        />

        <tooltip-btn
          icon="mdi-chevron-double-right"
          tooltip-text="Seek to track end"
          @click="$emit('seek', track.end)"
        />
      </template>
      <tooltip-btn
        v-else
        icon="mdi-map-marker"
        tooltip-text="Seek to detection"
        @click="$emit('seek', track.begin)"
      />

      <tooltip-btn
        v-if="!merging"
        :icon="(editing) ? 'mdi-pencil-box' : 'mdi-pencil-box-outline'"
        tooltip-text="Toggle edit mode"
        :disabled="!inputValue"
        @click="handler.trackEdit(track.trackId)"
      />
    </v-row>
  </div>
</template>

<style lang="scss" scoped>
.track-item {
  border-radius: inherit;

  .item-row {
    width: 100%;
  }

  .trackNumber {
    font-family: monospace;
    max-width: 80px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    &:hover {
      cursor: pointer;
      font-weight: bolder;
      text-decoration: underline;
    }
  }
  .input-box {
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 4px;
    padding: 0 6px;
    width: 135px;
    color: white;
  }
  .select-input {
    width: 120px;
    background-color: #1e1e1e;
    appearance: menulist;
  }
  .type-color-box {
    margin: 7px;
    margin-top: 4px;
    min-width: 15px;
    max-width: 15px;
    min-height: 15px;
    max-height: 15px;
  }
}
</style>
