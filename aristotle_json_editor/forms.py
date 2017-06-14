from django import forms
from jsonschema import Draft4Validator, validate
from jsonschema.validators import RefResolutionError, RefResolver
import json
"""
SET A CUstom resolver
"""

class AristotleLocalRefResolver(RefResolver):

    def resolve(self, ref):
        if ref.startswith("/"):
            ref = ref[1:]
        url = self._urljoin_cache(self.resolution_scope, ref)
        
        # The commented bit causes a big circular loop, need to resolve.
        return url, {} #self._remote_cache(ref)


class JSONSchemaForm(forms.Form):
    schema = None
    json_data = forms.CharField(widget=forms.HiddenInput) #label='Your name', max_length=100)

    def __init__(self, *args, **kwargs):
        self.schema = kwargs.pop('schema')
        Draft4Validator.check_schema(self.schema)
        super(JSONSchemaForm, self).__init__(*args, **kwargs)


    def clean_json_data(self):
        json_data = self.cleaned_data['json_data']

        import os

        x = "file://"+os.path.dirname(os.path.abspath(__file__))+'/schemas/'

        data = json.loads(json_data) #self.data['json_data'])
        validator = Draft4Validator(
            schema=self.schema, 
            resolver=AristotleLocalRefResolver(base_uri=x, referrer=self.schema)
        )
        valid = validator.validate(data)
        for i in validator.iter_errors(data):
            print("error", i)
        if valid is not None:
            raise forms.ValidationError("There was an error validating this JSON document")
        return data
