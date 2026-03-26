import subprocess

from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.conf import settings

from panel.utils import read_config

class ChangelogView(TemplateView):
    template_name = 'upgrade.html'

    def get_context_data(self, **kwargs):
        context = super(ChangelogView, self).get_context_data(**kwargs)

        # Call script to obtain the changelog lines and split
        changelog = subprocess.check_output(['sudo', settings.QBO_UPDATE_SCRIPT, 'update', 'changelog']) \
            .decode('utf-8').split('\n')

        # Avoid array with an empty result
        if changelog and not changelog[0]:
            changelog = None

        context['changelog'] = changelog

        if read_config()['distro'] == settings.IBMWATSON_DISTRO:
            context['backSettings'] = True
        else:
            context['backSettings'] = False

        return context


class UpdatingView(View):
    template_name = 'updating.html'

    def post(self, request, **kwargs):

        # Call update script
        subprocess.Popen(['sudo', settings.QBO_UPDATE_SCRIPT, 'update'])

        return render(request, self.template_name)

    def get(self, request):
        return redirect('upgrade')
