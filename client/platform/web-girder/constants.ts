import { GirderModel } from '@girder/components/src';
import { DatasetMeta, DatasetMetaMutable, DatasetType } from 'dive-common/apispec';

/**
 * Static properties loaded from the girder folder data/metadata
 */
interface GirderMetadataStatic extends DatasetMetaMutable {
  id: string;
  type: Readonly<DatasetType | 'multi'>;
  fps: Readonly<number>;
  name: string;
  createdAt: string;
  ffprobe_info?: Record<string, string>;
  annotate: boolean;
  foreign_media_id?: string;
}

/** A girder folder model with dataset metadata */
interface GirderDatasetModel extends GirderModel {
  meta: GirderMetadataStatic;
}

/**
 * Full metadata including dynamic properties (image list, video url)
 */
type GirderMetadata = GirderMetadataStatic & DatasetMeta;

export {
  GirderDatasetModel,
  GirderMetadataStatic,
  GirderMetadata,
};
