import logging

import requests
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import Address, to_python
from .widgets import AddressWidget


logger = logging.getLogger(__name__)


__all__ = ['AddressWidget', 'AddressField']


if not settings.GOOGLE_API_KEY:
    raise ImproperlyConfigured("GOOGLE_API_KEY is not configured in settings.py")


def ensure_correct_datatypes(value):
    # Make sure lat/long are floats if present.
    float_fields = ['latitude', 'longitude']
    for field in float_fields:
        if field in value:
            value[field] = ensure_float(value, field)


def ensure_float(value, field):
    if value[field]:
        try:
            return float(value[field])
        except Exception:
            raise forms.ValidationError(
                'Invalid value for %(field)s',
                code='invalid',
                params={'field': field}
            )
    else:
        return None


class AddressField(forms.ModelChoiceField):
    widget = AddressWidget
    non_raw_fields = {
        'country', 'country_code', 'state', 'state_code', 'locality', 'sublocality',
        'postal_code', 'street_number', 'route', 'subpremise', 'latitude', 'longitude',
    }

    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = Address.objects.none()
        super().__init__(*args, **kwargs)

    def try_geocode(self, value):
        """If we only have raw, see if we can do better using the Google Geocode API (Autocomplete
        currently doesn't handle subpremise).
        """
        if isinstance(value, dict):
            if self.non_raw_fields & value.keys():
                return False
        return True

    def to_python(self, value):
        # Treat `None`s and empty strings as empty.
        if value is None or value == '':
            return None
        ensure_correct_datatypes(value)
        if self.try_geocode(value):
            value = GeocodeRaw(value['raw']).geocode()
        return to_python(value)


class GeocodeRaw:

    def __init__(self, raw):
        self.geocode_api = 'https://maps.googleapis.com/maps/api/geocode/json'
        # We need some minimum components to use a raw address with the Geocode API or it could try
        # to use the wrong region as the viewport and give a bogus result, but not say it's a guess.
        self.min_components_for_geocode = len('address street city state/country'.split())
        self.raw = raw

    def can_geocode(self):
        return len(self.raw.split()) >= self.min_components_for_geocode

    def verify_one_result(self, results):
        if len(results) > 1:
            # TODO: offer these as suggestions?
            raise forms.ValidationError(
                'Too many results for %(raw)s',
                code='too_many_results',
                params={'raw': self.raw}
            )

    def verify_not_partial(self, result):
        if 'partial_match' in result:
            raise forms.ValidationError(
                'Only a partial match could be found for %(raw)s',
                code='partial',
                params={'raw': self.raw}
            )

    def verify_not_approximate(self, result):
        if 'geometry' in result and 'location_type' in result['geometry']:
            loc_type = result['geometry']['location_type']
            if loc_type != 'ROOFTOP':
                raise forms.ValidationError(
                    'Only an approximate match could be found for %(raw)s',
                    code='approximate',
                    params={'raw': self.raw}
                )

    def get_address_components_dict(self, address_components):
        ac = {}
        ac_map = {
            'administrative_area_level_1': 'state_code',
            'country': 'country_code',
        }
        for component in address_components:
            try:
                component_types = component['types']
                if 'political' in component_types:
                    component_types.remove('political')
                component_type = ac_map.get(component['types'][0], component['types'][0])
                if component_type.endswith('_code'):
                    ac[component_type.replace('_code', '')] = component['long_name']
                ac[component_type] = component['short_name']
            except (KeyError, IndexError):
                # Could be there are no types, or the type isn't one we know how to deal with.
                pass
        return ac

    def flatten(self, result):
        address_components = self.get_address_components_dict(result['address_components'])
        value = {
            'country': address_components.get('country'),
            'country_code': address_components.get('country_code'),
            'locality': address_components.get('locality'),
            'postal_code': address_components.get('postal_code'),
            'route': address_components.get('route'),
            'subpremise': address_components.get('subpremise'),
            'street_number': address_components.get('street_number'),
            'state': address_components.get('state'),
            'state_code': address_components.get('state_code'),
            'formatted': result.get('formatted_address'),
            'latitude': result.get('geometry').get('location')['lat'],
            'longitude': result.get('geometry').get('location')['lng'],
        }
        return value

    def geocode(self):
        if not self.can_geocode():
            return self.raw
        data = {'address': self.raw.replace(' ', '+'), 'key': settings.GOOGLE_API_KEY}
        r = requests.get(self.geocode_api, params=data)
        if r.status_code == requests.codes.ok:
            # Most requests will succeed, as Google will try to find matches, so we have to check
            # the data to see if it is what we really wanted.
            results = r.json()['results']
            self.verify_one_result(results)
            result = results[0]
            # Subpremise might result in a partial match.
            potential_error = None
            try:
                self.verify_not_partial(result)
            except forms.ValidationError as e:
                potential_error = e
            self.verify_not_approximate(result)
            value = self.flatten(result)
            if value['subpremise'] and value['subpremise'] in self.raw:
                potential_error = None
            if potential_error:
                raise potential_error
            ensure_correct_datatypes(value)
            value['raw'] = self.raw
            return value
