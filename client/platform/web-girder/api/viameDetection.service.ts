import { DatasetType, SaveAttributeArgs, SaveDetectionsArgs } from 'dive-common/apispec';
import { TrackData } from 'vue-media-annotator/track';
import girderRest from '../plugins/girder';

export interface ExportUrlsResponse {
  mediaType: DatasetType;
  exportAllUrl: string;
  exportMediaUrl: string;
  exportDetectionsUrl: string;
  currentThresholds: Record<string, number>;
}

interface SerializedTrackstore {
  [key: number]: TrackData;
}

async function getExportUrls(
  id: string,
  excludeBelowThreshold: boolean,
): Promise<ExportUrlsResponse> {
  return (await girderRest.get<ExportUrlsResponse>(`viame_detection/${id}/export`, {
    params: { excludeBelowThreshold },
  })).data;
}

async function loadDetections(folderId: string, formatting = 'track_json') {
  const { data } = await girderRest.get('viame_detection', {
    params: { folderId, formatting },
  });
  return data as { [key: string]: TrackData };
}

async function saveDetections(folderId: string, args: SaveDetectionsArgs) {
  return girderRest.put('viame_detection', {
    upsert: args.upsert,
    delete: args.delete,
  }, {
    params: { folderId },
  });
}

async function saveAttributes(folderId: string, args: SaveAttributeArgs) {
  return girderRest.put('viame_attribute', {
    upsert: args.upsert,
    delete: args.delete,
  }, {
    params: { folderId },
  });
}


interface ClipMetaResponse {
  videoUrl: string;
}

async function getClipMeta(folderId: string) {
  const { data } = await girderRest.get('viame_detection/clip_meta', {
    params: { folderId },
  });
  return data as ClipMetaResponse;
}

interface MultiMetaResponse {
  folderId: string;
  type: DatasetType;
}
export {
  getClipMeta,
  getExportUrls,
  loadDetections,
  saveDetections,
  saveAttributes,
};
