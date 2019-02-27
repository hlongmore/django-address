import logging
import time

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

    def __init__(self, *args, **kwargs):
        kwargs['queryset'] = Address.objects.none()
        super().__init__(*args, **kwargs)

    def try_geocode(self, value):
        """If we only have raw, or raw is the only key whose value is not False in a boolean
        context, see if we can do better using the Google Geocode API (Autocomplete currently
        doesn't handle subpremise). This of course requires we have raw data.
        """
        if isinstance(value, dict):
            no_raw_no_empty = {k: v for k, v in value.items() if v and k != 'raw'}
            if no_raw_no_empty:
                return False
            if not value.get('raw'):
                return False
        return True

    def to_python(self, value):
        # Treat `None`s and empty strings as empty.
        if value is None or value == '':
            return None
        if self.try_geocode(value):
            value = GeocodeRaw(value['raw']).geocode()
        ensure_correct_datatypes(value)
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
        value = self.raw
        potential_errors = []
        if not self.can_geocode():
            return value
        tries = {'raw': self.raw, 'formatted': ''}
        for t in tries:
            data = {'address': tries[t].replace(' ', '+'), 'key': settings.GOOGLE_API_KEY}
            r = requests.get(self.geocode_api, params=data, headers={'Cache-Control': 'no-cache'})
            if r.status_code == requests.codes.ok:
                value, potential_error = self.process_result(r)
                if potential_error:
                    potential_errors.append(potential_error)
                    if value.get('subpremise'):
                        raw_subpremise = self.get_raw_subpremise(value['raw'])
                        if settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE:
                            # Try again using the formatted address, but use the subpremise from the raw data.
                            other_subpremise = f"#{value['subpremise']}"
                            tries['formatted'] = value['formatted'].replace(
                                other_subpremise, f'#{raw_subpremise}')
                            # Don't freak out the Google servers by submitting requests one right
                            # after the other
                            time.sleep(0.75)
                        elif settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY:
                            useable_address_data = all(
                                [
                                    self.raw.startswith(value['street_number']),
                                    value.get('latitude'),
                                    value.get('longitude'),
                                ]
                            )
                            if useable_address_data:
                                value['subpremise'] = raw_subpremise
                                potential_errors = []
                                break
                else:
                    break
        if potential_errors:
            # Raise the original error.
            raise potential_errors[0]
        return value

    def process_result(self, api_result):
        # Most requests will succeed, as Google will try to find matches, so we have to check
        # the data to see if it is what we really wanted.
        results = api_result.json()['results']
        self.verify_one_result(results)
        result = results[0]
        # A partial match could indicate the address includes a subpremise. Also, the correct
        # address could be found but the wrong subpremise (e.g. by not having commas in 'raw'.
        potential_error = None
        try:
            self.verify_not_partial(result)
        except forms.ValidationError as e:
            potential_error = e
        self.verify_not_approximate(result)
        value = self.flatten(result)
        if value['subpremise'] and value['subpremise'] in self.raw:
            potential_error = None
        value['raw'] = self.raw
        return value, potential_error

    def get_raw_subpremise(self, raw):
        """Try to find the subpremise, accounting for a possible space between the '#' and the
        value. We're not going to try to get APT, STE, etc. here, just '#'.
        """
        hash_index = -1
        components = raw.split()
        for i, v in enumerate(components):
            if v.startswith('#'):
                v = v.replace('#', '').strip()
                if v:
                    return v
                hash_index = i
                break
        if hash_index > 2:
            return components[hash_index + 1]
        return ''
