import IntervalTree from '@flatten-js/interval-tree';
import {
  provide, inject, ref, Ref,
} from '@vue/composition-api';

import { StateStyles, TypeStyling } from './use/useStyling';
import { EditAnnotationTypes } from './layers/EditAnnotationLayer';
import Track, { TrackId } from './track';
import { VisibleAnnotationTypes } from './layers';
import { RectBounds } from './utils';

/**
 * Type definitions are read only because injectors may mutate internal state,
 * but should never overwrite or delete the injected object.
 */

const AllTypesSymbol = Symbol('allTypes');
type AllTypesType = Readonly<Ref<readonly string[]>>;

const UsedTypesSymbol = Symbol('usedTypes');
type UsedTypesType = Readonly<Ref<readonly string[]>>;

const CheckedTrackIdsSymbol = Symbol('checkedTrackIds');
type CheckedTrackIdsType = Readonly<Ref<readonly TrackId[]>>;

const CheckedTypesSymbol = Symbol('checkedTypes');
type CheckedTypesType = Readonly<Ref<readonly string[]>>;

const EnabledTracksSymbol = Symbol('enabledTracks');
type EnabledTracksType = Readonly<Ref<readonly Track[]>>;

const EditingModeSymbol = Symbol('editingMode');
type EditingModeType = Readonly<Ref<false | EditAnnotationTypes>>;

const FrameSymbol = Symbol('frame');
type FrameType = Readonly<Ref<number>>;

const IntervalTreeSymbol = Symbol('intervalTree');
type IntervalTreeType = Readonly<IntervalTree>;

const TrackMapSymbol = Symbol('trackMap');
type TrackMapType = Readonly<Map<TrackId, Track>>;

const TracksSymbol = Symbol('tracks');
type TracksType = Readonly<Ref<readonly Track[]>>;

const TypeStylingSymbol = Symbol('typeStyling');
type TypeStylingType = Readonly<Ref<TypeStyling>>;

const SelectedKeySymbol = Symbol('selectedKey');
type SelectedKeyType = Readonly<Ref<string>>;

const SelectedTrackIdSymbol = Symbol('selectedTrackId');
type SelectedTrackIdType = Readonly<Ref<TrackId | null>>;

const StateStylesSymbol = Symbol('stateStyles');
type StateStylesType = Readonly<StateStyles>;

const VisibleModesSymbol = Symbol('visibleModes');
type VisibleModesType = Readonly<Ref<readonly VisibleAnnotationTypes[]>>;

/**
 * Handler interface describes all global events mutations
 * for above state
 */
export interface Handler {
  /* Select and seek to track */
  trackSeek(trackId: TrackId): void;
  /* Toggle editing mode for track */
  trackEdit(trackId: TrackId): void;
  /* set checked track ids */
  trackEnable(trackId: TrackId, value: boolean): void;
  /* toggle selection mode for track */
  trackSelect(trackId: TrackId | null, edit: boolean): void;
  /* select next track in the list */
  trackSelectNext(delta: number): void;
  /* split track */
  trackSplit(trackId: TrackId | null, frame: number): void;
  /* Change tracks difinitive type */
  trackTypeChange(trackId: TrackId | null, value: string): void;
  /* Add new empty track and select it */
  trackAdd(): TrackId;
  /* update Rectangle bounds for track */
  updateRectBounds(
    frameNum: number,
    flick: number | undefined,
    bounds: RectBounds,
  ): void;
  /* update geojson for track */
  updateGeoJSON(
    eventType: 'in-progress' | 'editing',
    frameNum: number,
    flick: number | undefined,
    data: GeoJSON.Feature,
    key?: string,
    preventInterrupt?: () => void,
  ): void;
  /* Remove a whole track */
  removeTrack(trackIds: TrackId[]): void;
  /* Remove a single point from selected track's geometry by selected index */
  removePoint(): void;
  /* Remove an entire annotation from selected track by selected key */
  removeAnnotation(): void;
  /* set selectFeatureHandle and selectedKey */
  selectFeatureHandle(i: number, key: string): void;
  /* set checked type strings */
  setCheckedTypes(types: string[]): void;
  /* set checked type strings */
  removeTypeTracks(types: string[]): void;
  /* removes an individual type */
  deleteType(types: string): void;
  /* Change type name */
  updateTypeName({ currentType, newType }: { currentType: string; newType: string }): void;
  /* change styles */
  updateTypeStyle(args: {
    type: string;
    color?: string;
    strokeWidth?: number;
    opacity?: number;
    fill?: boolean;
  }): void;
}
const HandlerSymbol = Symbol('handler');

/**
 * Make a trivial noop handler. Useful if you only intend to
 * override some small number of values.
 * @param handle callbacl for all handler methods
 */
function dummyHandler(handle: (name: string, args: unknown[]) => void): Handler {
  return {
    trackSeek(...args) { handle('trackSeek', args); },
    trackEdit(...args) { handle('trackEdit', args); },
    trackEnable(...args) { handle('trackEnable', args); },
    trackSelect(...args) { handle('trackSelect', args); },
    trackSelectNext(...args) { handle('trackSelectNext', args); },
    trackSplit(...args) { handle('trackSplit', args); },
    trackTypeChange(...args) { handle('trackTypeChange', args); },
    trackAdd(...args) { handle('trackAdd', args); return 0; },
    updateRectBounds(...args) { handle('updateRectBounds', args); },
    updateGeoJSON(...args) { handle('updateGeoJSON', args); },
    removeTrack(...args) { handle('removeTrack', args); },
    removePoint(...args) { handle('removePoint', args); },
    removeAnnotation(...args) { handle('removeAnnotation', args); },
    selectFeatureHandle(...args) { handle('selectFeatureHandle', args); },
    setCheckedTypes(...args) { handle('setCheckedTypes', args); },
    removeTypeTracks(...args) { handle('removeTypeTracks', args); },
    deleteType(...args) { handle('deleteType', args); },
    updateTypeName(...args) { handle('updateTypeName', args); },
    updateTypeStyle(...args) { handle('updateTypeStyle', args); },
  };
}

/**
 * State interface describes the reactive properties that should be provided
 * by a vue-media-annotator consumer.
 *
 * Implementations of most of this state is provided via src/use, but some
 * you will need to construct on your own.
 */
export interface State {
  allTypes: AllTypesType;
  usedTypes: UsedTypesType;
  checkedTrackIds: CheckedTrackIdsType;
  checkedTypes: CheckedTypesType;
  editingMode: EditingModeType;
  enabledTracks: EnabledTracksType;
  frame: FrameType;
  intervalTree: IntervalTreeType;
  trackMap: TrackMapType;
  tracks: TracksType;
  typeStyling: TypeStylingType;
  selectedKey: SelectedKeyType;
  selectedTrackId: SelectedTrackIdType;
  stateStyles: StateStylesType;
  visibleModes: VisibleModesType;
}

/**
 * make a trivial state store. Useful if you only
 * intend to override some small number of values.
 */
function dummyState(): State {
  const style = {
    strokeWidth: 2,
    opacity: 1,
    color: 'white',
    fill: false,
  };
  return {
    allTypes: ref([]),
    usedTypes: ref([]),
    checkedTrackIds: ref([]),
    checkedTypes: ref([]),
    editingMode: ref(false),
    enabledTracks: ref([]),
    frame: ref(0),
    intervalTree: new IntervalTree(),
    trackMap: new Map<TrackId, Track>(),
    tracks: ref([]),
    typeStyling: ref({
      color() { return style.color; },
      strokeWidth() { return style.strokeWidth; },
      opacity() { return style.opacity; },
      fill() { return style.fill; },
    }),
    selectedKey: ref(''),
    selectedTrackId: ref(null),
    stateStyles: {
      disabled: style,
      selected: style,
      standard: style,
    },
    visibleModes: ref(['rectangle', 'text'] as VisibleAnnotationTypes[]),
  };
}

/**
 * Provide global state and handler for a single instance
 * of vue-media-annotator.  Multiple annotator windows
 * are currently not supported.
 *
 * @param {State} state
 * @param {Hander} handler
 */
function provideAnnotator(state: State, handler: Handler) {
  provide(AllTypesSymbol, state.allTypes);
  provide(UsedTypesSymbol, state.usedTypes);
  provide(CheckedTrackIdsSymbol, state.checkedTrackIds);
  provide(CheckedTypesSymbol, state.checkedTypes);
  provide(EnabledTracksSymbol, state.enabledTracks);
  provide(EditingModeSymbol, state.editingMode);
  provide(FrameSymbol, state.frame);
  provide(IntervalTreeSymbol, state.intervalTree);
  provide(TrackMapSymbol, state.trackMap);
  provide(TracksSymbol, state.tracks);
  provide(TypeStylingSymbol, state.typeStyling);
  provide(SelectedKeySymbol, state.selectedKey);
  provide(SelectedTrackIdSymbol, state.selectedTrackId);
  provide(StateStylesSymbol, state.stateStyles);
  provide(VisibleModesSymbol, state.visibleModes);
  provide(HandlerSymbol, handler);
}

function _handleMissing(s: symbol): Error {
  return new Error(`Missing provided object for symbol ${s.toString()}: must provideAnnotator()`);
}

function use<T>(s: symbol) {
  const v = inject<T>(s);
  if (v === undefined) {
    throw _handleMissing(s);
  }
  return v;
}

function useAllTypes() {
  return use<AllTypesType>(AllTypesSymbol);
}
function useUsedTypes() {
  return use<UsedTypesType>(UsedTypesSymbol);
}

function useCheckedTrackIds() {
  return use<CheckedTrackIdsType>(CheckedTrackIdsSymbol);
}

function useCheckedTypes() {
  return use<CheckedTypesType>(CheckedTypesSymbol);
}

function useEnabledTracks() {
  return use<EnabledTracksType>(EnabledTracksSymbol);
}

function useEditingMode() {
  return use<EditingModeType>(EditingModeSymbol);
}

function useFrame() {
  return use<FrameType>(FrameSymbol);
}

function useHandler() {
  return use<Handler>(HandlerSymbol);
}

function useIntervalTree() {
  return use<IntervalTreeType>(IntervalTreeSymbol);
}

function useTrackMap() {
  return use<TrackMapType>(TrackMapSymbol);
}

function useTracks() {
  return use<TracksType>(TracksSymbol);
}

function useTypeStyling() {
  return use<TypeStylingType>(TypeStylingSymbol);
}

function useSelectedKey() {
  return use<SelectedKeyType>(SelectedKeySymbol);
}

function useSelectedTrackId() {
  return use<SelectedTrackIdType>(SelectedTrackIdSymbol);
}

function useStateStyles() {
  return use<StateStylesType>(StateStylesSymbol);
}

function useVisibleModes() {
  return use<VisibleModesType>(VisibleModesSymbol);
}

export {
  dummyHandler,
  dummyState,
  provideAnnotator,
  use,
  useAllTypes,
  useUsedTypes,
  useCheckedTrackIds,
  useCheckedTypes,
  useEnabledTracks,
  useEditingMode,
  useHandler,
  useIntervalTree,
  useFrame,
  useTrackMap,
  useTracks,
  useTypeStyling,
  useSelectedKey,
  useSelectedTrackId,
  useStateStyles,
  useVisibleModes,
};
