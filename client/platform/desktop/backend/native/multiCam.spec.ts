/// <reference types="jest" />
import mockfs from 'mock-fs';
import fs from 'fs-extra';
import { Console } from 'console';

import type {
  MultiCamImportFolderArgs,
  MultiCamImportKeywordArgs,
} from 'dive-common/apispec';
import type {
  ConversionArgs,
  DesktopJob,
  DesktopJobUpdate,
  DesktopJobUpdater,
  Settings,
  MultiCamDesktop,
} from 'platform/desktop/constants';

import beginMultiCamImport from './multiCamImport';

const settings: Settings = {
  version: 1,
  dataPath: '/home/user/viamedata',
  viamePath: '/opt/viame',
};
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const updater = (update: DesktopJobUpdate) => undefined;
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const checkMedia = async (settingsVal: Settings, file: string) => ({
  websafe: file.includes('mp4'),
  originalFpsString: '30/1',
  originalFps: 30,
});
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const convertMedia = async (settingsVal: Settings, args: ConversionArgs,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  updaterFunc: DesktopJobUpdater) => ({
  key: 'jobKey',
  title: 'title',
  command: 'command',
  args: {},
  jobType: 'conversion',
  datasetIds: ['datasetId'],
  pid: 1234,
  workingDir: 'workingdir',
  exitCode: null,
  startTime: new Date(),
} as DesktopJob);
// https://github.com/tschaub/mock-fs/issues/234
// eslint-disable-next-line @typescript-eslint/no-unused-vars
const console = new Console(process.stdout, process.stderr);
const multiCamSetup = fs.readJSONSync('../testutils/multicam.spec.json');

mockfs(multiCamSetup.mockfs);

type FolderTest = Record<string, {
  input: MultiCamImportFolderArgs;
  output: {
    multiCam: MultiCamDesktop;
    mediaConvertList?: string[];
  };
}>;

type Keyword = Record<string, {
  input: MultiCamImportKeywordArgs;
  output: {
    multiCam: MultiCamDesktop;
    mediaConvertList?: string[];
  };
}>;

type FailingFolder = Record<string, {
  input: MultiCamImportFolderArgs;
  output: {
    error: string;
  };
}>;

type FailingKeyword= Record<string, {
  input: MultiCamImportKeywordArgs;
  output: {
    error: string;
  };
}>;

describe('native.multiCamImport', () => {
  if (multiCamSetup.folderTests) {
    const folderTests = (multiCamSetup.folderTests as FolderTest);
    Object.entries(folderTests).forEach(([key, val]) => {
      it(`Test Folder Import: ${key}`, async () => {
        const output = await beginMultiCamImport(settings, val.input, checkMedia);
        expect(output.jsonMeta.multiCam).toEqual(val.output.multiCam);
        expect(output.mediaConvertList).toEqual(val.output.mediaConvertList);
      });
    });
  }
  if (multiCamSetup.keywordTests) {
    const keywordTests = (multiCamSetup.keywordTests as Keyword);
    Object.entries(keywordTests).forEach(([key, val]) => {
      it(`Test Keyword Import: ${key}`, async () => {
        const output = await beginMultiCamImport(settings, val.input, checkMedia);
        expect(output.jsonMeta.multiCam).toEqual(val.output.multiCam);
        expect(output.mediaConvertList).toEqual(val.output.mediaConvertList);
      });
    });
  }
  if (multiCamSetup.failingFolderTests) {
    const failingFolderTests = (multiCamSetup.failingFolderTests as FailingFolder);
    Object.entries(failingFolderTests).forEach(([key, val]) => {
      it(`Failing Folder Test: ${key}`, async () => {
        await expect(beginMultiCamImport(settings, val.input, checkMedia))
          .rejects.toThrow(val.output.error);
      });
    });
  }
  if (multiCamSetup.failingKeywordTests) {
    const failingKeywordTests = (multiCamSetup.failingKeywordTests as FailingKeyword);
    Object.entries(failingKeywordTests).forEach(([key, val]) => {
      it(`Failing Folder Test: ${key}`, async () => {
        await expect(beginMultiCamImport(settings, val.input, checkMedia))
          .rejects.toThrow(val.output.error);
      });
    });
  }
});


afterAll(() => {
  mockfs.restore();
});
