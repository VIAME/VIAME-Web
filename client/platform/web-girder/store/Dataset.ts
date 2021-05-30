import { Module } from 'vuex';

import {
  ImageSequenceType, MediaTypes, VideoType,
} from 'dive-common/constants';
import type { FrameImage, MultiCamMedia } from 'dive-common/apispec';

import type { GirderMetadataStatic, GirderMetadata } from 'platform/web-girder/constants';
import { getFolder, getItemDownloadUri } from 'platform/web-girder/api/girder.service';
import { getValidWebImages, MultiCamWeb } from 'platform/web-girder/api/viame.service';
import { getClipMeta } from 'platform/web-girder/api/viameDetection.service';

import { DatasetState, RootState } from './types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isGirderDatasetMeta(obj: any): obj is GirderMetadataStatic {
  if (obj.annotate !== true) {
    return false;
  }
  if (!(typeof obj.name === 'string')) {
    return false;
  }
  if (!(typeof obj.type === 'string')) {
    return false;
  }
  if (!(obj.type in MediaTypes)) {
    return false;
  }
  if (!(typeof obj.id === 'string')) {
    return false;
  }
  if (!(typeof obj.fps === 'number')) {
    return false;
  }
  return true;
}

async function getImageSequence(baseFolderId: string) {
  const items = await getValidWebImages(baseFolderId);
  return items.map((item) => ({
    url: getItemDownloadUri(item._id),
    filename: item.name,
  }));
}

async function getVideoUrl(baseFolderId: string) {
  const clipMeta = await getClipMeta(baseFolderId);
  if (!clipMeta.videoUrl) {
    throw new Error('Expected clipMeta.videoUrl, but was empty.');
  }
  return clipMeta.videoUrl;
}
const datasetModule: Module<DatasetState, RootState> = {
  namespaced: true,
  state: {
    meta: null,
  },
  mutations: {
    set(state, { dataset }: { dataset: GirderMetadata }) {
      state.meta = dataset;
    },
  },
  actions: {
    async load({ commit }, datasetId: string): Promise<GirderMetadata> {
      const girderDataset = await getFolder(datasetId);
      const dsMeta = {
        id: girderDataset._id,
        ...girderDataset,
        ...(girderDataset.meta as Record<string, unknown>),
      };

      let videoUrl = '';
      let imageData = [] as FrameImage[];
      let multiCamMedia: MultiCamMedia | null = null;

      if (!dsMeta) {
        throw new Error(`could not fetch dataset for id ${datasetId}`);
      }

      if (!isGirderDatasetMeta(dsMeta)) {
        throw new Error(`girder folder ${datasetId} could not be parsed as dataset`);
      }

      const baseType = dsMeta.type;
      const baseFolderId = dsMeta._id;
      let subType = null;
      /* Load media based on dataset */
      if (dsMeta.type === 'multi' && dsMeta.meta.multiCam) {
        //We need to get the default display data type
        const multiCam = (dsMeta.meta.multiCam as MultiCamWeb);
        subType = dsMeta.meta.subType || null;
        if (multiCam.cameras) {
          const pairs = Object.entries(multiCam.cameras);
          multiCamMedia = {
            cameras: {},
            display: multiCam.display,
          };
          for (let i = 0; i < pairs.length; i += 1) {
            const [key, item] = pairs[i];
            let subVideoUrl = '';
            let subImageData = [] as FrameImage[];
            if (item.type === VideoType) {
              // eslint-disable-next-line no-await-in-loop
              subVideoUrl = await getVideoUrl(item.originalBaseId);
            } else if (item.type === ImageSequenceType) {
              // eslint-disable-next-line no-await-in-loop
              subImageData = await getImageSequence(item.originalBaseId);
            } else {
              throw new Error(`Unable to load media for dataset type: ${dsMeta.type}`);
            }
            multiCamMedia.cameras[key] = {
              type: item.type,
              videoUrl: subVideoUrl,
              imageData: subImageData,
            };
          }
        }
      } else if (baseType === VideoType) {
        videoUrl = await getVideoUrl(baseFolderId);
      } else if (baseType === ImageSequenceType) {
        imageData = await getImageSequence(baseFolderId);
      } else {
        throw new Error(`Unable to load media for dataset type: ${dsMeta.type}`);
      }
      // These aren't part of the native girder meta, must derive them
      const meta: GirderMetadata = {
        ...dsMeta,
        videoUrl,
        imageData,
        multiCamMedia,
        subType,
      };
      meta.type = baseType;
      commit('set', { dataset: meta });
      commit('Location/setLocation', {
        _id: dsMeta.parentId,
        _modelType: dsMeta.parentCollection,
      }, { root: true });
      return meta;
    },
  },
};

export default datasetModule;
