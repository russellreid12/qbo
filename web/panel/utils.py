import yaml

from django.conf import settings

FOLDER_NAME = settings.QBO_FOLDER
FILE_NAME = 'config.yml'
FULL_FILE_NAME = '{}{}'.format(FOLDER_NAME, FILE_NAME)

def read_config():
    try:
        with open(FULL_FILE_NAME, 'r') as stream:
            try:
                return yaml.safe_load(stream)

            except yaml.YAMLError:
                # Can't load actual config
                pass

    except EnvironmentError:
        # Can't load actual config
        pass
