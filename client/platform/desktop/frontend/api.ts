import type { FileFilter } from 'electron';

import npath from 'path';
import axios, { AxiosInstance } from 'axios';
import { ipcRenderer, remote } from 'electron';

import type {
  DatasetMetaMutable, DatasetType, MultiCamImportArgs,
  Pipe, Pipelines, SaveAttributeArgs, SaveDetectionsArgs, TrainingConfigs,
} from 'dive-common/apispec';

import { fileVideoTypes, calibrationFileTypes, inputAnnotationFileTypes } from 'dive-common/constants';
import {
  DesktopJob, DesktopMetadata, JsonMeta, NvidiaSmiReply,
  RunPipeline, RunTraining, ExportDatasetArgs,
  MediaImportPayload,
} from 'platform/desktop/constants';


/**
 * Native functions that run entirely in the renderer
 */

async function openFromDisk(datasetType: DatasetType | 'calibration' | 'annotation', directory = false) {
  let filters: FileFilter[] = [];
  if (datasetType === 'video') {
    filters = [
      { name: 'Videos', extensions: fileVideoTypes },
      { name: 'All Files', extensions: ['*'] },
    ];
  }
  if (datasetType === 'calibration') {
    filters = [
      { name: 'calibration', extensions: calibrationFileTypes },
      { name: 'All Files', extensions: ['*'] },
    ];
  }
  if (datasetType === 'annotation') {
    filters = [
      { name: 'annotation', extensions: inputAnnotationFileTypes },
      { name: 'All Files', extensions: ['*'] },
    ];
  }
  const props = datasetType === 'image-sequence' || directory ? 'openDirectory' : 'openFile';
  const results = await remote.dialog.showOpenDialog({
    properties: [props],
    filters,
  });
  return results;
}


/**
 * IPC api for small-body messages
 */

function nvidiaSmi(): Promise<NvidiaSmiReply> {
  return ipcRenderer.invoke('nvidia-smi');
}

function openLink(url: string): Promise<void> {
  return ipcRenderer.invoke('open-link-in-browser', url);
}

async function getPipelineList(): Promise<Pipelines> {
  return ipcRenderer.invoke('get-pipeline-list');
}

async function getTrainingConfigurations(): Promise<TrainingConfigs> {
  return ipcRenderer.invoke('get-training-configs');
}

async function runPipeline(itemId: string, pipeline: Pipe): Promise<DesktopJob> {
  const args: RunPipeline = {
    pipeline,
    datasetId: itemId,
  };
  return ipcRenderer.invoke('run-pipeline', args);
}

async function runTraining(
  folderIds: string[], pipelineName: string, config: string, annotatedFramesOnly: boolean,
): Promise<DesktopJob> {
  const args: RunTraining = {
    datasetIds: folderIds,
    pipelineName,
    trainingConfig: config,
    annotatedFramesOnly,
  };
  return ipcRenderer.invoke('run-training', args);
}

function importMedia(path: string): Promise<MediaImportPayload> {
  return ipcRenderer.invoke('import-media', { path });
}

function importMultiCam(args: MultiCamImportArgs):
   Promise<MediaImportPayload> {
  return ipcRenderer.invoke('import-multicam-media', { args });
}

function importAnnotationFile(id: string, path: string): Promise<boolean> {
  return ipcRenderer.invoke('import-annotation', { id, path });
}

function finalizeImport(args: MediaImportPayload): Promise<JsonMeta> {
  return ipcRenderer.invoke('finalize-import', args);
}

async function exportDataset(
  id: string, exclude: boolean, typeFilter: readonly string[],
): Promise<string> {
  const location = await remote.dialog.showSaveDialog({
    title: 'Export Dataset',
    defaultPath: npath.join(remote.app.getPath('home'), `result_${id}.csv`),
  });
  if (!location.canceled && location.filePath) {
    const args: ExportDatasetArgs = {
      id, exclude, path: location.filePath, typeFilter: new Set(typeFilter),
    };
    return ipcRenderer.invoke('export-dataset', args);
  }
  return '';
}

/**
 * REST api for larger-body messages
 */

/**
 * Initialize an axios client instance given the server
 * address details fetched from backend over ipc
 */
let _axiosClient: AxiosInstance; // do not use elsewhere
async function getClient(): Promise<AxiosInstance> {
  if (_axiosClient === undefined) {
    const addr = await ipcRenderer.invoke('server-info');
    const baseURL = `http://${addr.address}:${addr.port}/api`;
    _axiosClient = axios.create({ baseURL });
  }
  return _axiosClient;
}

async function loadMetadata(id: string) {
  const client = await getClient();
  const { data } = await client.get<DesktopMetadata>(`dataset/${id}/meta`);
  return data;
}

async function saveMetadata(id: string, args: DatasetMetaMutable) {
  const client = await getClient();
  return client.post(`dataset/${id}/meta`, args);
}

async function saveDetections(id: string, args: SaveDetectionsArgs) {
  const client = await getClient();
  return client.post(`dataset/${id}/detections`, args);
}


async function saveAttributes(id: string, args: SaveAttributeArgs) {
  const client = await getClient();
  return client.post(`dataset/${id}/attributes`, args);
}

export {
  /* Standard Specification APIs */
  loadMetadata,
  getPipelineList,
  runPipeline,
  getTrainingConfigurations,
  runTraining,
  saveMetadata,
  saveDetections,
  saveAttributes,
  openFromDisk,
  /* Nonstandard APIs */
  exportDataset,
  finalizeImport,
  importMedia,
  importAnnotationFile,
  importMultiCam,
  openLink,
  nvidiaSmi,
};
