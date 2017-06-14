from django.conf.urls import url, include
from django.views.generic import TemplateView
from django.utils.translation import ugettext_lazy as _

from . import views
from aristotle_mdr import models as MDR

from aristotle_mdr.contrib.generic.views import (
    GenericAlterOneToManyView,
    GenericAlterManyToManyView
)

patterns = ([
    url(r'^account/quick_start', views.QuickStart.as_view(), name='quick_start_dashboard'),
    url(r'^json_edit/schemas/(?P<schema_name>.+).schema', views.ServeSchema.as_view(), name='serve_schema'),
    url(r'^json_edit/editor/(?P<schema_name>.+)', views.LoadEditor.as_view(), name='load_editor'),
    url(r'^json_edit/success', views.Success.as_view(), name='success'),
], 'aristotle_json_editor')

urlpatterns = [
    url(r'^', include(patterns)),
]