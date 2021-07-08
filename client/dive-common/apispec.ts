import { provide } from '@vue/composition-api';

import { use } from 'vue-media-annotator/provides';
import { TrackData, TrackId } from 'vue-media-annotator/track';
import { Attribute } from 'vue-media-annotator/use/useAttributes';
import { CustomStyle } from 'vue-media-annotator/use/useStyling';

type DatasetType = 'image-sequence' | 'video';
type MultiTrackRecord = Record<string, TrackData>;
type SubType = 'stereo' | 'multicam' | null; // Additional type info used for UI display enabled pipelines

interface Pipe {
  name: string;
  pipe: string;
  type: string;
}

interface Category {
  description: string;
  pipes: Pipe[];
}

interface TrainingConfigs {
  configs: string[];
  default: string;
}

type Pipelines = Record<string, Category>;

interface SaveDetectionsArgs {
  delete: TrackId[];
  upsert: TrackData[];
}

interface SaveAttributeArgs {
  delete: string[];
  upsert: Attribute[];
}

interface FrameImage {
  url: string;
  filename: string;
}

export interface MultiCamImportFolderArgs {
  defaultDisplay: string; // In multicam the default camera to display
  folderList: Record<string, string>; // Camera name and folder import for images or file for videos
  calibrationFile?: string; // NPZ calibation matrix file
  type: 'image-sequence' | 'video';
}

export interface MultiCamImportKeywordArgs {
  defaultDisplay: string; // In multicam the default camera to display
  keywordFolder: string; // Base folder used for import, globList will filter folder
  globList: Record<string, string>; // Camera name key and glob pattern for keywordfolder
  calibrationFile?: string; // NPZ calibration matrix file
  type: 'image-sequence'; // Always image-sequence type for glob matching
}

export type MultiCamImportArgs = MultiCamImportFolderArgs | MultiCamImportKeywordArgs;

export interface HTMLFileReferences {
  mediaHTMLFileList: Record<string, File[]>;
  calibrationHTMLFile?: File;
}

interface MultiCamMedia {
  cameras: Record<string, {
    type: DatasetType;
    imageData: FrameImage[];
    videoUrl: string;
  }>;
  defaultDisplay: string; // Default camera for displaying the MultiCamMedia
}

interface MediaImportResponse {
  jsonMeta: {
    originalImageFiles: string[];
  };
  globPattern: string;
  mediaConvertList: string[];
}
/**
 * The parts of metadata a user should be able to modify.
 */
interface DatasetMetaMutable {
  customTypeStyling?: Record<string, CustomStyle>;
  confidenceFilters?: Record<string, number>;
}

interface DatasetMeta extends DatasetMetaMutable {
  id: Readonly<string>;
  imageData: Readonly<FrameImage[]>;
  videoUrl: Readonly<string | undefined>;
  type: Readonly<DatasetType | 'multi'>;
  fps: Readonly<number>; // this will become mutable in the future.
  name: Readonly<string>;
  createdAt: Readonly<string>;
  attributes?: Readonly<Record<string, Attribute>>;
}

interface Api {

  getPipelineList(): Promise<Pipelines>;
  runPipeline(itemId: string, pipeline: Pipe): Promise<unknown>;

  getTrainingConfigurations(): Promise<TrainingConfigs>;
  runTraining(
    folderIds: string[], pipelineName: string, config: string, annotatedFramesOnly: boolean
  ): Promise<unknown>;

  loadMetadata(datasetId: string): Promise<DatasetMeta>;
  loadDetections(datasetId: string): Promise<MultiTrackRecord>;

  saveDetections(datasetId: string, args: SaveDetectionsArgs): Promise<unknown>;
  saveMetadata(datasetId: string, metadata: DatasetMetaMutable): Promise<unknown>;
  saveAttributes(datasetId: string, args: SaveAttributeArgs): Promise<unknown>;
  // Non-Endpoint shared functions
  openFromDisk(datasetType: DatasetType | 'calibration' | 'annotation', directory?: boolean):
    Promise<{canceled?: boolean; filePaths: string[]; fileList?: File[]; root?: string}>;
  importAnnotationFile(id: string, path: string, file?: File): Promise<boolean>;
}
const ApiSymbol = Symbol('api');

/**
 * provideApi specifies an implementation of the data persistence interface
 * for use in vue-web-common
 * @param api an api implementation
 */
function provideApi(api: Api) {
  provide(ApiSymbol, api);
}

function useApi() {
  return use<Readonly<Api>>(ApiSymbol);
}

export {
  provideApi,
  useApi,
};

export type {
  Api,
  DatasetMeta,
  DatasetMetaMutable,
  DatasetType,
  SubType,
  FrameImage,
  MultiTrackRecord,
  Pipe,
  Pipelines,
  SaveDetectionsArgs,
  SaveAttributeArgs,
  TrainingConfigs,
  MultiCamMedia,
  MediaImportResponse,
};
