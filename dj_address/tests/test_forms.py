from django.conf import settings
from django.core.exceptions import ValidationError as CoreValidationError
from django.test import TestCase
from django.forms import ValidationError, Form
from dj_address.forms import AddressField, AddressWidget


class TestForm(Form):
    address = AddressField()


class AddressFieldTestCase(TestCase):

    def setUp(self):
        self.form = TestForm()
        self.field = self.form.base_fields['address']
        self.missing_state = {
            'country': 'UK',
            'locality': 'Somewhere',
            'postal_code': '34904',
            'route': 'A street?',
            'street_number': '3',
            'raw': '3 A street?, Somewhere, UK',
        }
        self.old_replace = settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY
        self.old_retry = settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE
        self.old_ignore = settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE

    def tearDown(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = self.old_replace
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = self.old_retry
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = self.old_ignore

    def test_to_python_none(self):
        self.assertEqual(self.field.to_python(None), None)

    def test_to_python_empty(self):
        self.assertEqual(self.field.to_python(''), None)

    def test_to_python_invalid_lat_lng(self):
        self.assertRaises(ValidationError, self.field.to_python, {'latitude': 'x'})
        self.assertRaises(ValidationError, self.field.to_python, {'longitude': 'x'})

    def test_to_python_invalid_empty_lat_lng(self):
        self.assertEqual(self.field.to_python({'latitude': ''}), None)
        self.assertEqual(self.field.to_python({'longitude': ''}), None)

    def test_to_python_no_locality(self):
        input = {
            'country': 'United States',
            'country_code': 'US',
            'state': 'New York',
            'state_code': 'NY',
            'locality': '',
            'sublocality': 'Brooklyn',
            'postal_code': '11201',
            'route': 'Joralemon St',
            'street_number': '209',
            'raw': '209 Joralemon Street, Brooklyn, NY, United States'
        }
        res = self.field.to_python(input)
        self.assertEqual('Brooklyn', res.locality.name)

    def test_to_python_subpremise_in_dict(self):
        input = {
            'country': 'United States',
            'country_code': 'US',
            'state': 'New York',
            'state_code': 'NY',
            'locality': '',
            'sublocality': 'Brooklyn',
            'postal_code': '11201',
            'route': 'Joralemon St',
            'street_number': '209',
            'subpremise': '300',
            'raw': '209 Joralemon Street #300, Brooklyn, NY, United States'
        }
        res = self.field.to_python(input)
        self.assertEqual('Brooklyn', res.locality.name)
        self.assertEqual('300', res.subpremise)

    # TODO: Fix
    # def test_to_python_empty_state(self):
    #     val = self.field.to_python(self.missing_state)
    #     self.assertTrue(isinstance(val, Address))
    #     self.assertNotEqual(val.locality, None)

    def test_has_invalid_subpremise_in_raw(self):
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = False
        input = {
            'raw': '209 Joralemon Street #300, Brooklyn, NY, United States'
        }
        with self.assertRaisesMessage(
                CoreValidationError,
                'Only a partial match could be found for 209 Joralemon Street #300,'
                ' Brooklyn, NY, United States') as e:
            self.field.to_python(input)

    def test_has_invalid_subpremise_in_raw_ignore_missing(self):
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = True
        input = {
            'raw': '209 Joralemon Street #300, Brooklyn, NY, United States'
        }
        res = self.field.to_python(input)
        self.assertEqual('Brooklyn', res.locality.name)
        self.assertEqual('300', res.subpremise)

    def test_too_many_results_from_geocode(self):
        input = {
            'raw': '1 Nowhere Street, Dublin, UT 84095'
        }
        with self.assertRaisesMessage(
                CoreValidationError,
                'Too many results for 1 Nowhere Street, Dublin, UT 84095'):
            self.field.to_python(input)

    def test_has_valid_subpremise_in_raw(self):
        input = {
            'raw': '10897 South River Front Parkway #200, South Jordan, UT'
        }
        res = self.field.to_python(input)
        self.assertEqual('South Jordan', res.locality.name)
        self.assertEqual('200', res.subpremise)
        self.assertEqual('84095', res.locality.postal_code)
        self.assertEqual('S River Front Pkwy', res.route)

    # The next few tests deal with inconsistencies in the Google Geocode API. For example,
    # sometimes what is submitted in the raw request will impact what is returned in unexpected
    # ways. Consider the following two addresses, which are identical but for punctuation:
    # 10653 S River Front Pkwy #300 South Jordan UT 84095
    # vs.
    # 10653 S River Front Pkwy #300, South Jordan, UT 84095
    # The latter correctly gets subpremise = '300', the former gets subpremise = '100', which is
    # valid for the street address, but not what we were looking for.
    # Also, consider
    # 10653 S River Front Pkwy #300, South Jordan, UT 84095, USA
    # The only difference is between that and the middle one is the addition of ', USA'. But now no
    # subpremise is returned.
    def test_substitute_subpremise_for_partial_match(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = True
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = False
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10653 S River Front Pkwy #300 South Jordan UT 84095'
        }
        res = self.field.to_python(input)
        self.assertEqual('300', res.subpremise)
        self.assertEqual('South Jordan', res.locality.name)
        self.assertEqual('10653', res.street_number)
        self.assertEqual('S River Front Pkwy', res.route)
        self.assertTrue('300' in res.formatted)

    def test_retry_using_formatted_for_partial_match(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = False
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = True
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = False
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10653 S River Front Pkwy #300 South Jordan UT 84095'
        }
        # If Google ever fixes the reliability of their API, this test should start failing with the
        # expected error not being raised.
        with self.assertRaisesMessage(
                CoreValidationError,
                'Only a partial match could be found for 10653 S River Front Pkwy #300 '
                'South Jordan UT 84095'):
            self.field.to_python(input)

    def test_retry_using_formatted_for_partial_match_ignore_missing(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = False
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = True
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = True
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10653 S River Front Pkwy #300 South Jordan UT 84095'
        }
        res = self.field.to_python(input)
        self.assertEqual('300', res.subpremise)
        self.assertEqual('South Jordan', res.locality.name)
        self.assertEqual('10653', res.street_number)
        self.assertEqual('S River Front Pkwy', res.route)
        self.assertTrue('300' in res.formatted)

    def test_substitute_subpremise_raw_includes_country(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = True
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = False
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = True
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10653 S River Front Pkwy #300, South Jordan, UT 84095, USA'
        }
        res = self.field.to_python(input)
        self.assertEqual('300', res.subpremise)
        self.assertEqual('South Jordan', res.locality.name)
        self.assertEqual('10653', res.street_number)
        self.assertEqual('S River Front Pkwy', res.route)
        self.assertTrue('300' in res.formatted)

    def test_retry_using_formatted_raw_includes_country(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = False
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = True
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = False
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10653 S River Front Pkwy #300, South Jordan, UT 84095, USA'
        }
        # If Google ever fixes the reliability of their API, this test should start failing with the
        # expected error not being raised.
        with self.assertRaisesMessage(
                CoreValidationError,
                'Only a partial match could be found for 10653 S River Front Pkwy #300, '
                'South Jordan, UT 84095, USA'):
            self.field.to_python(input)

    def test_retry_using_formatted_raw_includes_country_ignore_mising(self):
        settings.DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = False
        settings.DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = True
        settings.DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = True
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10653 S River Front Pkwy #300, South Jordan, UT 84095, USA'
        }
        res = self.field.to_python(input)
        self.assertEqual('300', res.subpremise)
        self.assertEqual('South Jordan', res.locality.name)
        self.assertEqual('10653', res.street_number)
        self.assertEqual('S River Front Pkwy', res.route)
        self.assertTrue('300' in res.formatted)

    def test_geocode_all_fields_present_only_raw_has_data(self):
        input = {
            'country': '',
            'country_code': '',
            'state': '',
            'state_code': '',
            'locality': '',
            'sublocality': '',
            'postal_code': '',
            'route': '',
            'street_number': '',
            'subpremise': '',
            'raw': '10897 South River Front Parkway #200, South Jordan, UT'
        }
        res = self.field.to_python(input)
        self.assertEqual('South Jordan', res.locality.name)
        self.assertEqual('200', res.subpremise)
        self.assertEqual('84095', res.locality.postal_code)

    def test_to_python(self):
        res = self.field.to_python({'raw': 'Someplace'})
        self.assertEqual('Someplace', res.raw)

    def test_render(self):
        actual = self.form.as_table()
        expected = """\
<tr><th><label for="id_address">Address:</label></th><td><input type="text" name="address" class="address" required id="id_address">
<div id="address_components">
<input type="hidden" name="address_country" data-geo="country" value="" />
<input type="hidden" name="address_country_code" data-geo="country_short" value="" />
<input type="hidden" name="address_locality" data-geo="locality" value="" />
<input type="hidden" name="address_sublocality" data-geo="sublocality" value="" />
<input type="hidden" name="address_postal_code" data-geo="postal_code" value="" />
<input type="hidden" name="address_route" data-geo="route" value="" />
<input type="hidden" name="address_street_number" data-geo="street_number" value="" />
<input type="hidden" name="address_subpremise" data-geo="subpremise" value="" />
<input type="hidden" name="address_state" data-geo="administrative_area_level_1" value="" />
<input type="hidden" name="address_state_code" data-geo="administrative_area_level_1_short" value="" />
<input type="hidden" name="address_formatted" data-geo="formatted_address" value="" />
<input type="hidden" name="address_latitude" data-geo="lat" value="" />
<input type="hidden" name="address_longitude" data-geo="lng" value="" />
</div></td></tr>"""
        self.assertHTMLEqual(expected, actual)


class AddressWidgetTestCase(TestCase):

    def test_attributes_set_correctly(self):
        wid = AddressWidget(attrs={'size': '150'})
        self.assertEqual('150', wid.attrs['size'])
        html = wid.render('test', None)
        self.assertNotEqual(-1, html.find('size="150"'))
