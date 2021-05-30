import os
from pathlib import Path

from girder import events, plugin
from girder.constants import AccessType
from girder.models.setting import Setting
from girder.models.user import User
from girder.utility import mail_utils, setting_utilities
from girder.utility.model_importer import ModelImporter

from dive_utils.constants import (
    SETTINGS_CONST_JOBS_CONFIGS,
    UserPrivateQueueEnabledMarker,
)

from .client_webroot import ClientWebroot
from .event import process_fs_import, process_s3_import, send_new_user_email
from .viame import Viame
from .viame_detection import ViameDetection
from .viame_summary import SummaryItem, ViameSummary


@setting_utilities.validator({SETTINGS_CONST_JOBS_CONFIGS})
def validateSettings(doc):
    """
    Handle plugin-specific system settings. Right now we don't do any
    validation.
    """
    val = doc['value']
    if val is not None:
        # TODO: replace with real schema validation
        assert 'training' in val, '"training" missing from doc'
        assert 'pipelines' in val, '"pipelines" missing from doc'


class GirderPlugin(plugin.GirderPlugin):
    def load(self, info):
        ModelImporter.registerModel('summaryItem', SummaryItem, plugin='dive_server')
        User().exposeFields(AccessType.READ, UserPrivateQueueEnabledMarker)

        info["apiRoot"].viame = Viame()
        info["apiRoot"].viame_detection = ViameDetection()
        info["apiRoot"].viame_summary = ViameSummary()

        DIVE_MAIL_TEMPLATES = Path(os.path.realpath(__file__)).parent / 'mail_templates'
        mail_utils.addTemplateDirectory(str(DIVE_MAIL_TEMPLATES))

        # Relocate Girder
        info["serverRoot"], info["serverRoot"].girder = (
            ClientWebroot(),
            info["serverRoot"],
        )
        info["serverRoot"].api = info["serverRoot"].girder.api

        events.bind(
            "filesystem_assetstore_imported",
            "process_fs_import",
            process_fs_import,
        )
        events.bind(
            "s3_assetstore_imported",
            "process_s3_import",
            process_s3_import,
        )
        events.bind(
            'model.user.save.created',
            'send_new_user_email',
            send_new_user_email,
        )

        # Create dependency on worker
        plugin.getPlugin('worker').load(info)
        Setting().set(
            'worker.api_url',
            os.environ.get('WORKER_API_URL', 'http://girder:8080/api/v1'),
        )

        broker_url = os.environ.get('CELERY_BROKER_URL', None)
        if broker_url is None:
            raise RuntimeError('CELERY_BROKER_URL must be set')
        Setting().set('worker.broker', broker_url)
