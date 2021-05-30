import type { GirderModel } from '@girder/components/src';

import {
  CustomMediaImportPayload,
  DatasetMetaMutable,
  DatasetType,
  Pipe, Pipelines, SaveAttributeArgs, TrainingConfigs,
} from 'dive-common/apispec';
import {
  calibrationFileTypes, fileVideoTypes, inputAnnotationFileTypes,
  inputAnnotationTypes, otherImageTypes,
  otherVideoTypes, websafeImageTypes, websafeVideoTypes,
} from 'dive-common/constants';
import girderRest from '../plugins/girder';


export interface MultiCamWeb {
  cameras: Record<string, {
    originalBaseId: string;
    type: DatasetType;
  }>;
  display: string;
  calibration: string;
}
interface HTMLFile extends File {
  webkitRelativePath?: string;
}
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

function runTraining(folderIds: string[], pipelineName: string, config: string) {
  return girderRest.post('/viame/train', folderIds, { params: { pipelineName, config } });
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

function postProcess(folderId: string) {
  return girderRest.post(`viame/postprocess/${folderId}`);
}

function multiCamPostProcess(folderId: string,
  args: { defaultDisplay: string; folderList: Record<string, string[]>; calibrationFile: string}) {
  return girderRest.post(`viame/multicam_postprocess/${folderId}`, args);
}

async function importAnnotation(parentId: string, file: HTMLFile) {
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
async function openFromDisk(datasetType: DatasetType | 'calibration' | 'annotation', directory = false):
Promise<{ canceled: boolean; filePaths: string[]; fileList?: File[]; root?: string }> {
  const input: HTMLInputElement = document.createElement('input');
  input.type = 'file';
  const baseTypes: string[] = inputAnnotationFileTypes.map((item) => `.${item}`);
  input.multiple = true;
  if (directory) {
    // Webkit directory is necessary for loading a folder
    // eslint-disable-next-line @typescript-eslint/ban-ts-ignore
    //@ts-ignore
    input.webkitdirectory = true;
    input.multiple = false;
  }
  if (datasetType === 'image-sequence') {
    input.accept = baseTypes.concat(websafeImageTypes).concat(otherImageTypes).join(',');
  } else if (datasetType === 'video') {
    input.accept = baseTypes.concat(websafeVideoTypes).concat(otherVideoTypes)
      .concat(fileVideoTypes.map((item) => `.${item}`)).join(',');
  } else if (datasetType === 'calibration') {
    input.accept = calibrationFileTypes.map((item) => `.${item}`).join(',');
  } else if (datasetType === 'annotation') {
    input.accept = inputAnnotationTypes
      .concat(inputAnnotationFileTypes.map((item) => `.${item}`)).join(',');
  }
  return new Promise((resolve) => {
    input.onchange = (event) => {
      if (event) {
        const { files } = event.target as HTMLInputElement;
        if (files) {
          let fileList = Array.from(files) as HTMLFile[];
          let root;
          // Calculate the root and remove any recursive subdirectories
          if (fileList[0]?.webkitRelativePath !== undefined && directory) {
            root = fileList[0]?.webkitRelativePath.replace(`/${fileList[0].name}`, '');
            let filterType = ['application/octet-stream']
              .concat(inputAnnotationTypes);

            if (datasetType === 'image-sequence') {
              filterType = filterType
                .concat(websafeImageTypes)
                .concat(otherImageTypes);
            } else if (datasetType === 'video') {
              filterType = filterType
                .concat(websafeVideoTypes)
                .concat(otherVideoTypes);
            }
            fileList = fileList.filter((item) => {
              if (item.webkitRelativePath && item.webkitRelativePath.split('/').length > 2) {
                return false;
              }
              return filterType.includes(item.type);
            });
          }
          const response = {
            canceled: !files.length,
            fileList,
            filePaths: fileList.map((item) => item.name),
            root,
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
  });
}
async function importMedia(files: string[]): Promise<CustomMediaImportPayload> {
  return {
    jsonMeta: {
      originalImageFiles: files,
    },
    globPattern: '',
    mediaConvertList: [],
  };
}

export {
  clone,
  getBrandData,
  deleteResources,
  getPipelineList,
  makeViameFolder,
  postProcess,
  multiCamPostProcess,
  importAnnotation,
  runPipeline,
  getTrainingConfigurations,
  runTraining,
  saveMetadata,
  saveAttributes,
  setUsePrivateQueue,
  validateUploadGroup,
  getValidWebImages,
  openFromDisk,
  importMedia,
};
