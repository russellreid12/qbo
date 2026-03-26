from django.urls import re_path
from django.views.generic import TemplateView

from panel.views.home_views import HomeView
from panel.views.moves_views import MoveView
from panel.views.config_views import ConfigView
from panel.views.upgrade_views import ChangelogView, UpdatingView

urlpatterns = [

    # Home view
    re_path(r'^$', HomeView.as_view(), name='home'),

    # Only templates
    re_path(r'^checkers$', TemplateView.as_view(template_name='checkers-wrapper.html'), name='checkers'),
    re_path(r'^checkers-game$', TemplateView.as_view(template_name='checkers-game.html'), name='checkers-game'),

    # Upgrade
    re_path(r'^upgrade$', ChangelogView.as_view(), name='upgrade'),
    re_path(r'^updating', UpdatingView.as_view(), name='updating'),

    # Settings
    re_path(r'^settings$', ConfigView.as_view(template_name='settings.html'), name='settings'),

    # REST API
    re_path(r'^api/talk-move', MoveView.as_view(), name='talk-move'),
]
