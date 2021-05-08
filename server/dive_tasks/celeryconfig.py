import os
from logging import info, warn

from girder_client import GirderClient

from dive_tasks.tasks import app

# First, check to see if this is a private user queue runner
dive_username = os.environ.get('DIVE_USERNAME', None)
dive_password = os.environ.get('DIVE_PASSWORD', None)
dive_api_url = os.environ.get('DIVE_API_URL', 'https://viame.kitware.com/api/v1')
broker_url = os.environ.get('CELERY_BROKER_URL', None)

if dive_username and dive_password:
    info(
        """
        _    _________    __  _________   _       __           __
        | |  / /  _/   |  /  |/  / ____/  | |     / /___  _____/ /_____  _____
        | | / // // /| | / /|_/ / __/     | | /| / / __ \/ ___/ //_/ _ \/ ___/
        | |/ // // ___ |/ /  / / /___     | |/ |/ / /_/ / /  / ,< /  __/ /
        |___/___/_/  |_/_/  /_/_____/     |__/|__/\____/_/  /_/|_|\___/_/
        """
    )
    info(" You are running in private standalone mode.")
    info(" Authenticating...")
    # Fetch Celery broker credentials from server
    diveclient = GirderClient(apiUrl=dive_api_url)
    diveclient.authenticate(username=dive_username, password=dive_password)
    me = diveclient.get('user/me')
    creds = diveclient.post(f'rabbit_user_queues/user/{me["_id"]}')
    broker_url = creds['broker_url']
    queue_name = creds['username']
    if not me['user_private_queue_enabled']:
        warn(" Private queues not enabled for this user.")
        warn(" You can visit https://viame.kitware/com/#jobs to change these settings")
    info(" For support, please email viame-web@kitare.com")
    info("-------------------------------")
    task_default_queue = queue_name

if broker_url is None:
    raise RuntimeError('CELERY_BROKER_URL must be set')

broker_heartbeat = False
worker_send_task_events = False

# Remote control is necessary to handle cancellation
# Needs celery.pidbox, reply.celery.pidbox, uuid.reply.celery.pidbox, celery@uuid.celery.pidbox
worker_enable_remote_control = True

result_backend = None
task_ignore_result = True
