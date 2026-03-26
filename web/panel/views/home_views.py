from django.shortcuts import render
from django.views import View
from django.conf import settings

from panel.utils import read_config

class HomeView(View):

    template_name = 'home.html'
    template_name_watson = 'home-watson.html'

    def get(self, request):
        if read_config()['distro'] == settings.IBMWATSON_DISTRO:
            return render(request, self.template_name_watson)
        else:
            return render(request, self.template_name)
