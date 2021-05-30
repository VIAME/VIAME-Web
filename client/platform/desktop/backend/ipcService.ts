import OS from 'os';
import http from 'http';
import { ipcMain } from 'electron';
import { MultiCamImportArgs } from 'dive-common/apispec';
import {
  DesktopJobUpdate, RunPipeline, RunTraining, Settings, ExportDatasetArgs,
  MediaImportPayload,
} from 'platform/desktop/constants';

import linux from './native/linux';
import win32 from './native/windows';
import * as common from './native/common';
import beginMultiCamImport from './native/multiCamImport';
import settings from './state/settings';
import { listen } from './server';

// defaults to linux if win32 doesn't exist
const currentPlatform = OS.platform() === 'win32' ? win32 : linux;
if (OS.platform() === 'win32') {
  win32.initialize();
}

export default function register() {
  /**
   * Platform-agnostic methods
   */
  ipcMain.handle('server-info', async () => {
    const server = await new Promise<http.Server>((resolve) => listen(resolve));
    return server.address();
  });
  ipcMain.handle('get-pipeline-list', async () => {
    const ret = await common.getPipelineList(settings.get());
    return ret;
  });
  ipcMain.handle('get-training-configs', async () => {
    const ret = await common.getTrainingConfigs(settings.get());
    return ret;
  });
  ipcMain.handle('open-link-in-browser', (_, url: string) => {
    common.openLink(url);
  });
  ipcMain.on('update-settings', async (_, s: Settings) => {
    settings.set(s);
  });
  ipcMain.handle('export-dataset', async (_, args: ExportDatasetArgs) => {
    const ret = await common.exportDataset(settings.get(), args);
    return ret;
  });

  /**
   * Platform-dependent methods
   */

  ipcMain.handle('nvidia-smi', async () => {
    const ret = await currentPlatform.nvidiaSmi();
    return ret;
  });
  ipcMain.handle('default-settings', async () => {
    const defaults = currentPlatform.DefaultSettings;
    return defaults;
  });

  ipcMain.handle('import-media', async (event, { path }: { path: string }) => {
    const ret = await common.beginMediaImport(
      settings.get(), path, currentPlatform.checkMedia,
    );
    return ret;
  });

  ipcMain.handle('import-multicam-media', async (event, { args }:
    { args: MultiCamImportArgs }) => {
    const ret = await beginMultiCamImport(
      settings.get(), args, currentPlatform.checkMedia,
    );
    return ret;
  });

  ipcMain.handle('import-annotation', async (event, { id, path }: { id: string; path: string }) => {
    const ret = await common.annotationImport(
      settings.get(), id, path,
    );
    return ret;
  });


  ipcMain.handle('finalize-import', async (event, args: MediaImportPayload) => {
    const updater = (update: DesktopJobUpdate) => {
      event.sender.send('job-update', update);
    };
    const ret = await common.finalizeMediaImport(
      settings.get(), args, updater, currentPlatform.convertMedia,
    );
    return ret;
  });

  ipcMain.handle('validate-settings', async (_, s: Settings) => {
    const ret = await currentPlatform.validateViamePath(s);
    return ret;
  });
  ipcMain.handle('run-pipeline', async (event, args: RunPipeline) => {
    const updater = (update: DesktopJobUpdate) => {
      event.sender.send('job-update', update);
    };
    return currentPlatform.runPipeline(settings.get(), args, updater);
  });
  ipcMain.handle('run-training', async (event, args: RunTraining) => {
    const updater = (update: DesktopJobUpdate) => {
      event.sender.send('job-update', update);
    };
    return currentPlatform.train(settings.get(), args, updater);
  });
}
