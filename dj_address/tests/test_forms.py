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
        self.assertEqual(res.locality.name, 'Brooklyn')

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
        self.assertEqual(res.locality.name, 'Brooklyn')
        self.assertEqual(res.subpremise, '300')

    # TODO: Fix
    # def test_to_python_empty_state(self):
    #     val = self.field.to_python(self.missing_state)
    #     self.assertTrue(isinstance(val, Address))
    #     self.assertNotEqual(val.locality, None)

    def test_has_invalid_subpremise_in_raw(self):
        input = {
            'raw': '209 Joralemon Street #300, Brooklyn, NY, United States'
        }
        with self.assertRaisesMessage(
                CoreValidationError,
                'Only a partial match could be found for 209 Joralemon Street #300,'
                ' Brooklyn, NY, United States') as e:
            self.field.to_python(input)

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
        self.assertEqual(res.locality.name, 'South Jordan')
        self.assertEqual(res.subpremise, '200')
        self.assertEqual(res.locality.postal_code, '84095')
        self.assertEqual(res.route, 'S River Front Pkwy')

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
        self.assertEqual(res.locality.name, 'South Jordan')
        self.assertEqual(res.subpremise, '200')
        self.assertEqual(res.locality.postal_code, '84095')

    def test_to_python(self):
        res = self.field.to_python({'raw': 'Someplace'})
        self.assertEqual(res.raw, 'Someplace')

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
        self.assertEqual(wid.attrs['size'], '150')
        html = wid.render('test', None)
        self.assertNotEqual(html.find('size="150"'), -1)
