import type { GirderModel } from '@girder/components/src';

import {
  DatasetMetaMutable,
  DatasetType,
  Pipe, Pipelines, SaveAttributeArgs, TrainingConfigs,
} from 'dive-common/apispec';
import {
  calibrationFileTypes, inputAnnotationFileTypes, inputAnnotationTypes, otherImageTypes,
  otherVideoTypes, websafeImageTypes, websafeVideoTypes,
} from 'dive-common/constants';
import girderRest from '../plugins/girder';

interface ValidationResponse {
  ok: boolean;
  type: 'video' | 'image-sequence';
  media: string[];
  annotations: string[];
  message: string;
}

export interface BrandData {
  vuetify: unknown;
  favicon: string | null;
  logo: string;
  name: string;
  loginMessage: string;
}
interface HTMLFile extends File {
  webkitRelativePath?: string;
}

async function getBrandData(): Promise<BrandData> {
  const { data } = await girderRest.get<BrandData>('viame/brand_data');
  return data;
}

async function clone({ folderId, name, parentFolderId }: {
  folderId: string;
  parentFolderId: string;
  name?: string;
}) {
  const formData = new FormData();
  formData.set('parentFolderId', parentFolderId);
  if (name) {
    formData.set('name', name);
  }
  const { data } = await girderRest.post<GirderModel>(`viame/dataset/${folderId}/clone`, formData);
  return data;
}

function makeViameFolder({
  folderId, name, fps, type,
}: {
  folderId: string;
  name: string;
  fps: number;
  type: string;
}) {
  return girderRest.post(
    '/folder',
    `metadata=${JSON.stringify({
      fps,
      type,
    })}`,
    {
      params: { parentId: folderId, name },
    },
  );
}

function deleteResources(resources: Array<GirderModel>) {
  const formData = new FormData();
  formData.set(
    'resources',
    JSON.stringify({
      folder: resources
        .filter((resource) => resource._modelType === 'folder')
        .map((resource) => resource._id),
      item: resources
        .filter((resource) => resource._modelType === 'item')
        .map((resource) => resource._id),
    }),
  );
  return girderRest.post('resource', formData, {
    headers: { 'X-HTTP-Method-Override': 'DELETE' },
  });
}

async function getPipelineList() {
  const { data } = await girderRest.get<Pipelines>('viame/pipelines');
  return data;
}

function runPipeline(itemId: string, pipeline: Pipe) {
  return girderRest.post('/viame/pipeline', null, {
    params: {
      folderId: itemId,
      pipeline,
    },
  });
}

async function getTrainingConfigurations(): Promise<TrainingConfigs> {
  const { data } = await girderRest.get<TrainingConfigs>('/viame/training_configs');
  return data;
}

function runTraining(
  folderIds: string[], pipelineName: string, config: string, annotatedFramesOnly: boolean,
) {
  return girderRest.post('/viame/train', folderIds, {
    params: { pipelineName, config, annotatedFramesOnly },
  });
}

function saveMetadata(folderId: string, metadata: DatasetMetaMutable) {
  return girderRest.put(
    `/viame/metadata/${folderId}`,
    { ...metadata },
  );
}

function saveAttributes(folderId: string, args: SaveAttributeArgs) {
  return girderRest.put('/viame/attributes', {
    upsert: args.upsert,
    delete: args.delete,
  }, {
    params: { folderId },
  });
}

async function importAnnotationFile(parentId: string, path: string, file?: HTMLFile) {
  if (file === undefined) {
    return false;
  }
  const resp = await girderRest.post('/file', null, {
    params: {
      parentType: 'folder',
      parentId,
      name: file.name,
      size: file.size,
      mimeType: file.type,
    },
  });
  if (resp.status === 200) {
    const uploadResponse = await girderRest.post('file/chunk', file, {
      params: {
        uploadId: resp.data._id,
        offset: 0,
      },
      headers: { 'Content-Type': 'application/octet-stream' },
    });
    if (uploadResponse.status === 200) {
      const final = await girderRest.post(`viame/postprocess/${parentId}`, null, {
        params: {
          skipJobs: true,
        },
      });
      if (final.status === 200) {
        return true;
      }
    }
  }
  return false;
}

function postProcess(folderId: string) {
  return girderRest.post(`viame/postprocess/${folderId}`);
}

async function setUsePrivateQueue(userId: string, value = false): Promise<{
  'user_private_queue_enabled': boolean;
}> {
  const { data } = await girderRest.put(`viame/user/${userId}/use_private_queue`, null, {
    params: {
      privateQueueEnabled: value,
    },
  });
  return data;
}

async function validateUploadGroup(names: string[]): Promise<ValidationResponse> {
  const { data } = await girderRest.post<ValidationResponse>('viame/validate_files', names);
  return data;
}

async function getValidWebImages(folderId: string) {
  const { data } = await girderRest.get<GirderModel[]>('viame/valid_images', {
    params: { folderId },
  });
  return data;
}

async function openFromDisk(datasetType: DatasetType | 'calibration' | 'annotation'):
Promise<{ canceled: boolean; filePaths: string[]; fileList?: File[]}> {
  const input: HTMLInputElement = document.createElement('input');
  input.type = 'file';
  const baseTypes: string[] = inputAnnotationFileTypes.map((item) => `.${item}`);
  if (!['calbiration', 'annotation'].includes(datasetType)) {
    input.multiple = true;
  }
  if (datasetType === 'image-sequence') {
    input.accept = baseTypes.concat(websafeImageTypes).concat(otherImageTypes).join(',');
  } else if (datasetType === 'video') {
    input.accept = baseTypes.concat(websafeVideoTypes).concat(otherVideoTypes).join(',');
  } else if (datasetType === 'calibration') {
    input.accept = calibrationFileTypes.map((item) => `.${item}`).join(',');
  } else if (datasetType === 'annotation') {
    input.accept = inputAnnotationTypes
      .concat(inputAnnotationFileTypes.map((item) => `.${item}`)).join(',');
  }
  return new Promise(((resolve) => {
    input.onchange = (event) => {
      if (event) {
        const { files } = event.target as HTMLInputElement;
        if (files) {
          const fileList = Array.from(files);
          const response = {
            canceled: !files.length,
            fileList,
            filePaths: fileList.map((item) => item.name),
          };
          return resolve(response);
        }
      }
      return resolve({
        canceled: true,
        filePaths: [],
      });
    };
    input.click();
  }));
}

export {
  clone,
  getBrandData,
  deleteResources,
  getPipelineList,
  makeViameFolder,
  importAnnotationFile,
  postProcess,
  runPipeline,
  getTrainingConfigurations,
  runTraining,
  saveMetadata,
  saveAttributes,
  setUsePrivateQueue,
  validateUploadGroup,
  getValidWebImages,
  openFromDisk,
};
