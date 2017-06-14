from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import HttpResponseRedirect, Http404
from django.views.generic import TemplateView, FormView, View
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _

from django.http import HttpResponse
from django.contrib.contenttypes.models import ContentType

import aristotle_mdr as aristotle

from aristotle_mdr.contrib.generic.forms import HiddenOrderModelFormSet
from aristotle_mdr.perms import (
    user_can_view, user_can_edit, user_in_workgroup,
    user_is_workgroup_manager, user_can_change_status
)

from .forms import JSONSchemaForm
import os
import json
import collections

def get_quick_starters():
    from django.conf import settings
    qs = settings.ARISTOTLE_SETTINGS.get('QUICK_STARTERS', [])
    out = collections.OrderedDict()
    for q in qs:
        out[q] = {
            'name': q,
            'model': ContentType.objects.get(model=q).model_class()
        }
    return out


class SchemaFileMixin(object):
    def get_schema_file(self, name):
        # file_name = name.split("/")[-1].split("\\")[-1]
        name = name.replace("//", "/")
        if name.startswith('/'):
            name = name[1:]
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'schemas',
            "%s.schema"%name
        )


@method_decorator(login_required, name='dispatch')
class QuickStart(TemplateView):
    template_name  = "quick_start_editor/dashboard/quick_editor_main.html"

    def get_context_data(self, **kwargs):
        """
        Insert the form into the context dict.
        """
        
        kwargs['quick_starters'] = get_quick_starters()
        return super(QuickStart, self).get_context_data(**kwargs)


@method_decorator(login_required, name='dispatch')
class Success(TemplateView):
    template_name  = "aristotle_json_editor/success.html"

    def get_context_data(self, **kwargs):
        """
        Insert the form into the context dict.
        """

        kwargs['data'] = self.request.GET.get('data')
        uuids = self.request.GET.get('uuids').split(',')
        kwargs['items'] = aristotle.models._concept.objects.filter(uuid__in=uuids).select_subclasses()
        return super(Success, self).get_context_data(**kwargs)


@method_decorator(login_required, name='dispatch')
class LoadEditor(SchemaFileMixin, FormView):
    template_name  = "aristotle_json_editor/editor.html"
    form_class = JSONSchemaForm
    success_url = "/json_edit/success"

    def dispatch(self, request, *args, **kwargs):
        if self.kwargs['schema_name'] not in get_quick_starters():
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """
        Insert the form into the context dict.
        """

        kwargs['metadata_type'] = self.kwargs['schema_name']
        return super(LoadEditor, self).get_context_data(**kwargs)

    def get_form_kwargs(self):
        """
        Returns the keyword arguments for instantiating the form.
        """
        kwargs = super().get_form_kwargs()

        with open(self.get_schema_file(self.kwargs['schema_name']), 'r') as f:
            _schema = json.loads(f.read(), object_pairs_hook=collections.OrderedDict)

            kwargs.update(schema=_schema)
            return kwargs

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        from django.utils.http import urlencode
        
        content_type = ContentType.objects.get(model=self.kwargs['schema_name']).model_class()
        obj = form.cleaned_data['json_data']
        # extra = form.cleaned_data['extra_data']
        
        print(obj)
        s = Serialiser(obj)
        s.serialise(obj, content_type)

        url = self.get_success_url() + '?' + urlencode(
            {
                "data": form.data,
                "uuids": ",".join(map(str,s.uuids))
            }
        )
        
        return HttpResponseRedirect(url)


@method_decorator(login_required, name='dispatch')
class ServeSchema(View, SchemaFileMixin):
    content_type = "application/json"
    def get_template_names(self):
        return ['aristotle_json_editor/schemas/%s.schema' % self.kwargs['schema_name']]

    def get(self, *args, **kwargs):
        print(self.kwargs['schema_name'])
        with open(self.get_schema_file(self.kwargs['schema_name']), 'rb') as f:
            response = HttpResponse(content=f)
            response['Content-Type'] = 'application/json'
            return response

from aristotle_mdr.fields import ConceptForeignKey, ConceptManyToManyField

class Serialiser(object):
    def __init__(self, root, extra={}):
        self.root = root
        self.serialised_extras = {}
        self.items = []
        self.uuids = []
    
    @transaction.atomic()
    def serialise(self, data, obj_type, defaults={}):
        import copy
        values = copy.deepcopy(defaults)
        
        field_names = [f.name for f in obj_type._meta.get_fields()]
        related = []
        if data.get('__obj__', None) is not None:
            return data.get('__obj__', None)

        for key, value in data.items():
            if key == "uuid":
                # Remote users *do not* get to set the UUIDs, ever!
                continue
            if key == "__obj__":
                continue

            if key in field_names:
                field = obj_type._meta.get_field(key)
                if type(field) is ConceptForeignKey:

                    if value == {'uuid': ""}:
                        pass
                    elif len(value.keys()) == 1 and "uuid" in value.keys():
                        _uuid = value['uuid']
                        model_type = type(field.rel.remote_field.related_model())
                        if _uuid.startswith('local'):
                            path = _uuid.split("##",1)[-1]

                            obj = self.query_json(self.root, path)
                            if obj.get("__obj__", None):
                                self.serialised_extras[path] = obj.get("__obj__")
                            else:
                                extra_obj = self.serialise(obj, model_type)
                                obj["__obj__"] = extra_obj
                                self.serialised_extras[path] = extra_obj

                            values[key] = self.serialised_extras[path]
                        else:
                            values[key] = model_type.objects.get(uuid=_uuid)
                            print(values[key])
                    else:
                        new_obj_type = field.related_model
                        obj = self.serialise(value, new_obj_type)
                        values[key] = obj
                elif type(field) is ConceptManyToManyField:
                    pass #2/0
                else:
                    values[key] = value
                    print(values[key])
    
            if hasattr(obj_type, 'serialize_weak_entities'):
                if key in dict(obj_type.serialize_weak_entities).keys():
                    related.append((key, value))
        values = {
            k: v for k,v in values.items()
            if k in 
            [f.name for f in obj_type._meta.get_fields()]
        }

        new_obj = obj_type.objects.create(**values)
        data["__obj__"] = new_obj

        if hasattr(new_obj, 'uuid'):
            self.items.append(new_obj)
            self.uuids.append(new_obj.uuid)

        for key, value in related:
            sub_field = dict(obj_type.serialize_weak_entities).get(key)
            sub_field = getattr(obj_type, sub_field)
            sub_type = type(sub_field.rel.related_model())
            
            for v in value:
                self.serialise(v, sub_type, {sub_field.rel.remote_field.name: new_obj})
    
        return new_obj
    
    def query_json(self, json_obj, path):
        parts = path.split('.')
        if type(json_obj) is dict and parts[0] == "root":
            parts = parts[1:]
        obj = json_obj
        for part in parts:
            if hasattr(json_obj, 'keys'):
                json_obj = json_obj.get(part)
            else:
                part = int(part)
                json_obj = json_obj[part]
        return json_obj
