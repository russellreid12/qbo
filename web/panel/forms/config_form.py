import yaml
import os
import socket

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _


FOLDER_NAME = settings.QBO_FOLDER
FILE_NAME = 'config.yml'
FULL_FILE_NAME = '{}{}'.format(FOLDER_NAME, FILE_NAME)

DEFAULT_CONFIG = {
    # Common fields
    'distro': 'standalone',
    'language': 'english',
    'startWith': 'interactive-dialogflow',
    'volume': 100,
    'microphoneGain': 100,
    'camera': 0,
    'headYPosition': 39,
    'servoSpeed': 100,
    'SpeechToTextListeningTime': 5,

    # Standalone fields
    'tokenAPIai': '',
    'gassistant_proyectid': '',
    'dialogflowv2_projectid': '',

    # IBMWatson fields
    'AssistantAPIKey': '',
    'AssistantURL': '',
    'AssistantID': '',
    'TextToSpeechAPIKey': '',
    'TextToSpeechURL': '',
    'SpeechToTextAPIKey': '',
    'SpeechToTextURL': '',
    'VisualRecognitionAPIKey': '',
    'VisualRecognitionURL': '',
}


def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


class BaseConfigForm(forms.Form):
    """
    Common fields and tasks for config form
    """

    ip = forms.CharField(label=_('IP Address'), required=False, disabled=True)

    language = forms.ChoiceField(label=_('Language'), choices=(
        ('english', _('English')),
        ('spanish', _('Spanish'))
    ))

    startWith = forms.ChoiceField(label=_('Start with'), choices=())

    volume = forms.IntegerField(label=_('Volume'), min_value=0, max_value=100)

    microphoneGain = forms.ChoiceField(label=_('Microphone Gain'), choices=(
        (45, _('Minimum')),
        (60, _('Medium')),
        (100, _('Maximum'))
    ))

    camera = forms.ChoiceField(label=_('Default camera'), choices=(
        (0, _('Primary')),
        (1, _('Secondary'))
    ))

    headYPosition = forms.ChoiceField(label=_('Starting Head Position'), choices=(
        (100, _('Down')),
        (39, _('Medium')),
        (0, _('Up'))
    ))

    servoSpeed = forms.IntegerField(label=_('Head movement speed'), min_value=0, max_value=200)

    SpeechToTextListeningTime = forms.IntegerField(label=_('Listening Time (In seconds)'), min_value=0, max_value=20)

    def __init__(self, *args, **kwargs):
        """
        Set 'startWith' choices from a class method 'get_start_choices'
        :param args:
        :param kwargs:
        """
        super(BaseConfigForm, self).__init__(*args, **kwargs)
        self.fields['startWith'].choices = self.get_start_choices()

    @staticmethod
    def get_default_options():
        return DEFAULT_CONFIG.copy()

    @staticmethod
    def get_start_choices():
        return (
            ('develop', _('Development mode')),
            ('scratch', _('Scratch'))
        )

    @staticmethod
    def create_folder():
        """
        Create system folder if not exists
        :return:
        """
        if not os.path.exists(FOLDER_NAME):
            os.makedirs(FOLDER_NAME)

    @staticmethod
    def read_config():
        """
        Read the actual config to load the initial data for the form
        :return:
        """
        config = BaseConfigForm.get_default_options()

        try:
            with open(FULL_FILE_NAME, 'r') as stream:
                try:
                    # Merge with default config
                    config.update(yaml.safe_load(stream))

                except yaml.YAMLError:
                    # Can't load actual config
                    pass

        except EnvironmentError:
            # Can't load actual config
            pass

        config.update({'ip': get_ip()})

        return config

    def write_config(self):
        """
        Write the new config in the target file
        :return:
        """

        # Prevent IO Error
        self.create_folder()

        # Get copy of the actual config
        config = self.read_config()

        # Update with the form values
        config.update(self.cleaned_data)

        with open(FULL_FILE_NAME, 'w+') as openfile:
            yaml.safe_dump(config, openfile, default_flow_style=False)


class StandaloneConfigForm(BaseConfigForm):
    """
    Form for "standalone" distro
    """

    tokenAPIai = forms.CharField(label=_('Token Dialogflow'), required=False)

    gassistant_proyectid = forms.CharField(label=_('Google Assistant project ID'), required=False)

    dialogflowv2_projectid = forms.CharField(label=_('DialogFlow V2 project ID'), required=False)

    @staticmethod
    def get_start_choices():
        return super(StandaloneConfigForm, StandaloneConfigForm).get_start_choices() + (
            ('interactive-gassistant', _('Google Assistant')),
            ('interactive-dialogflow', _('Dialogflow')),
            ('interactive-dialogflow-v2', _('Dialogflow V2')),
            ('interactive-mycroft', _('MyCroft')),
        )


class IBMWatsonConfigForm(BaseConfigForm):
    """
    Form for "ibmwatson" distro
    """

    AssistantAPIKey = forms.CharField(label=_('Assistant API Key'), required=False)
    AssistantURL = forms.CharField(label=_('Assistant URL'), required=False)
    AssistantID = forms.CharField(label=_('Assistant ID'), required=False)
    TextToSpeechAPIKey = forms.CharField(label=_('TextToSpeech API Key'), required=False)
    TextToSpeechURL = forms.CharField(label=_('TextToSpeech URL'), required=False)
    SpeechToTextAPIKey = forms.CharField(label=_('SpeechToText API Key'), required=False)
    SpeechToTextURL = forms.CharField(label=_('SpeechToText URL'), required=False)
    VisualRecognitionAPIKey = forms.CharField(label=_('Visual Recognition API Key'), required=False)
    VisualRecognitionURL = forms.CharField(label=_('Visual Recognition URL'), required=False)

    @staticmethod
    def get_start_choices():
        return super(StandaloneConfigForm, StandaloneConfigForm).get_start_choices() + (
            ('ibm-watson', _('IBM Watson')),
        )
