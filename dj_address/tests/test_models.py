from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from dj_address.models import Address, Country, State, Locality, AddressField
from dj_address.models import to_python


class CountryTestCase(TestCase):

    def setUp(self):
        self.au = Country.objects.create(name='Australia', code='AU')
        self.nz = Country.objects.create(name='New Zealand', code='NZ')
        self.be = Country.objects.create(name='Belgium', code='BE')

    def test_ordering(self):
        qs = Country.objects.all()
        self.assertEqual(qs.count(), 3)
        self.assertEqual(qs[0].code, 'AU')
        self.assertEqual(qs[1].code, 'BE')
        self.assertEqual(qs[2].code, 'NZ')

    def test_unique_name(self):
        self.assertRaises(IntegrityError, Country.objects.create, name='Australia', code='**')

    def test_str(self):
        self.assertEqual(str(self.au), 'Australia')


class StateTestCase(TestCase):

    def setUp(self):
        self.au = Country.objects.create(name='Australia', code='AU')
        self.vic = State.objects.create(name='Victoria', code='VIC', country=self.au)
        self.tas = State.objects.create(name='Tasmania', code='TAS', country=self.au)
        self.qld = State.objects.create(name='Queensland', country=self.au)
        self.empty = State.objects.create(country=self.au)
        self.uk = Country.objects.create(name='United Kingdom', code='UK')
        self.uk_vic = State.objects.create(name='Victoria', code='VIC', country=self.uk)

    def test_required_country(self):
        self.assertRaises(IntegrityError, State.objects.create)

    def test_ordering(self):
        qs = State.objects.all()
        self.assertEqual(qs.count(), 5)
        self.assertEqual(qs[0].name, '')
        self.assertEqual(qs[1].name, 'Queensland')
        self.assertEqual(qs[2].name, 'Tasmania')
        self.assertEqual(qs[3].name, 'Victoria')
        self.assertEqual(qs[4].name, 'Victoria')

    def test_unique_name_country(self):
        State.objects.create(name='Tasmania', country=self.uk)
        self.assertRaises(IntegrityError, State.objects.create, name='Tasmania', country=self.au)

    def test_str(self):
        self.assertEqual(str(self.vic), 'Victoria, Australia')
        self.assertEqual(str(self.empty), 'Australia')


class LocalityTestCase(TestCase):

    def setUp(self):
        self.au = Country.objects.create(name='Australia', code='AU')
        self.uk = Country.objects.create(name='United Kingdom', code='UK')

        self.au_vic = State.objects.create(name='Victoria', code='VIC', country=self.au)
        self.au_tas = State.objects.create(name='Tasmania', code='TAS', country=self.au)
        self.au_qld = State.objects.create(name='Queensland', country=self.au)
        self.au_empty = State.objects.create(country=self.au)
        self.uk_vic = State.objects.create(name='Victoria', code='VIC', country=self.uk)

        self.au_vic_nco = Locality.objects.create(name='Northcote', postal_code='3070', state=self.au_vic)
        self.au_vic_mel = Locality.objects.create(name='Melbourne', postal_code='3000', state=self.au_vic)
        self.au_vic_ftz = Locality.objects.create(name='Fitzroy', state=self.au_vic)
        self.au_vic_empty = Locality.objects.create(state=self.au_vic)
        self.uk_vic_mel = Locality.objects.create(name='Melbourne', postal_code='3000', state=self.uk_vic)

    def test_required_state(self):
        self.assertRaises(IntegrityError, Locality.objects.create)

    def test_ordering(self):
        qs = Locality.objects.all()
        self.assertEqual(qs.count(), 5)
        self.assertEqual(qs[0].name, '')
        self.assertEqual(qs[1].name, 'Fitzroy')
        self.assertEqual(qs[2].name, 'Melbourne')
        self.assertEqual(qs[3].name, 'Northcote')
        self.assertEqual(qs[4].name, 'Melbourne')

    def test_unique_name_state(self):
        Locality.objects.create(name='Melbourne', state=self.au_vic)
        self.assertRaises(IntegrityError, Locality.objects.create, name='Melbourne', state=self.au_vic)

    def test_str(self):
        self.assertEqual(str(self.au_vic_mel), 'Melbourne, Victoria 3000, Australia')
        self.assertEqual(str(self.au_vic_ftz), 'Fitzroy, Victoria, Australia')
        self.assertEqual(str(self.au_vic_empty), 'Victoria, Australia')


class AddressTestCase(TestCase):

    def setUp(self):
        self.au = Country.objects.create(name='Australia', code='AU')
        self.uk = Country.objects.create(name='United Kingdom', code='UK')

        self.au_vic = State.objects.create(name='Victoria', code='VIC', country=self.au)
        self.au_tas = State.objects.create(name='Tasmania', code='TAS', country=self.au)
        self.au_qld = State.objects.create(name='Queensland', country=self.au)
        self.au_empty = State.objects.create(country=self.au)
        self.uk_vic = State.objects.create(name='Victoria', code='VIC', country=self.uk)

        self.au_vic_nco = Locality.objects.create(name='Northcote', postal_code='3070', state=self.au_vic)
        self.au_vic_mel = Locality.objects.create(name='Melbourne', postal_code='3000', state=self.au_vic)
        self.au_vic_ftz = Locality.objects.create(name='Fitzroy', state=self.au_vic)
        self.au_vic_empty = Locality.objects.create(state=self.au_vic)
        self.uk_vic_mel = Locality.objects.create(name='Melbourne', postal_code='3000', state=self.uk_vic)

        self.ad1 = Address.objects.create(street_number='1', route='Some Street', locality=self.au_vic_mel,
                                          raw='1 Some Street, Victoria, Melbourne')
        self.ad2 = Address.objects.create(street_number='10', route='Other Street', locality=self.au_vic_mel,
                                          raw='10 Other Street, Victoria, Melbourne')
        self.ad3 = Address.objects.create(street_number='1', route='Some Street', locality=self.au_vic_nco,
                                          raw='1 Some Street, Northcote, Victoria')
        self.ad_empty = Address.objects.create(locality=self.au_vic_nco, raw='Northcote, Victoria')
        self.ad_sublocality = Address.objects.create(
            street_number='1', route='Some Street', subpremise='300', locality=self.au_vic_nco,
            raw='1 Some Street #300, Northcote, Victoria')

    def test_required_raw(self):
        obj = Address.objects.create()
        self.assertRaises(ValidationError, obj.clean)

    def test_ordering(self):
        qs = Address.objects.all()
        self.assertEqual(qs.count(), 5)
        self.assertEqual(qs[0].route, 'Other Street')
        self.assertEqual(qs[1].route, 'Some Street')
        self.assertEqual(qs[2].route, '')
        self.assertEqual(qs[3].route, 'Some Street')
        self.assertEqual(qs[4].subpremise, '300')

    # def test_unique_street_address_locality(self):
    #     Address.objects.create(street_number='10', route='Other Street', locality=self.au_vic_nco)
    #     self.assertRaises(
    #         IntegrityError, Address.objects.create,
    #         street_number='10', route='Other Street', locality=self.au_vic_mel
    #     )

    def test_str(self):
        self.assertEqual(str(self.ad1), '1 Some Street, Melbourne, Victoria 3000, Australia')
        self.assertEqual(str(self.ad_empty), 'Northcote, Victoria 3070, Australia')
        self.assertEqual(str(self.ad_sublocality),
                         '1 Some Street #300, Northcote, Victoria 3070, Australia')


class AddressFieldTestCase(TestCase):

    def setUp(self):
        self.ad1_dict = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'locality': 'Northcote',
            'postal_code': '3070',
            'state': 'Victoria',
            'state_code': 'VIC',
            'country': 'Australia',
            'country_code': 'AU'
        }
        self.address = AddressField()

    def test_assignment_from_dict(self):
        self.address = to_python(self.ad1_dict)
        self.assertEqual(self.address.raw, self.ad1_dict['raw'])
        self.assertEqual(self.address.street_number, self.ad1_dict['street_number'])
        self.assertEqual(self.address.route, self.ad1_dict['route'])
        self.assertEqual(self.address.subpremise, '')
        self.assertEqual(self.address.locality.name, self.ad1_dict['locality'])
        self.assertEqual(self.address.locality.postal_code, self.ad1_dict['postal_code'])
        self.assertEqual(self.address.locality.state.name, self.ad1_dict['state'])
        self.assertEqual(self.address.locality.state.code, self.ad1_dict['state_code'])
        self.assertEqual(self.address.locality.state.country.name, self.ad1_dict['country'])
        self.assertEqual(self.address.locality.state.country.code, self.ad1_dict['country_code'])

    def test_assignment_from_dict_with_subpremise(self):
        ad2_dict = {
            'raw': '10855 S River Front Pkwy #300, South Jordan, UT, US',
            'street_number': '10855',
            'route': 'River Front Pkwy',
            'subpremise': '300',
            'locality': 'South Jordan',
            'postal_code': '84095',
            'state': 'Utah',
            'state_code': 'UT',
            'country': 'United States',
            'country_code': 'US'
        }
        subpremise_address = to_python(ad2_dict)
        self.assertEqual(subpremise_address.raw, ad2_dict['raw'])
        self.assertEqual(subpremise_address.street_number, ad2_dict['street_number'])
        self.assertEqual(subpremise_address.route, ad2_dict['route'])
        self.assertEqual(subpremise_address.subpremise, ad2_dict['subpremise'])
        self.assertEqual(subpremise_address.locality.name, ad2_dict['locality'])
        self.assertEqual(subpremise_address.locality.postal_code, ad2_dict['postal_code'])
        self.assertEqual(subpremise_address.locality.state.name, ad2_dict['state'])
        self.assertEqual(subpremise_address.locality.state.code, ad2_dict['state_code'])
        self.assertEqual(subpremise_address.locality.state.country.name, ad2_dict['country'])
        self.assertEqual(subpremise_address.locality.state.country.code, ad2_dict['country_code'])

    def test_assignment_from_dict_no_country(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'locality': 'Northcote',
            'state': 'Victoria',
        }
        self.address = to_python(ad)
        self.assertEqual(self.address.raw, ad['raw'])
        self.assertEqual(self.address.street_number, '')
        self.assertEqual(self.address.route, '')
        self.assertEqual(self.address.locality, None)

    def test_assignment_from_dict_no_state(self):
        ad = {
            'raw': 'Somewhere',
            'locality': 'Northcote',
            'country': 'Australia',
        }
        self.address = to_python(ad)
        self.assertEqual(self.address.raw, ad['raw'])
        self.assertEqual(self.address.street_number, '')
        self.assertEqual(self.address.route, '')
        self.assertEqual(self.address.locality, None)

    def test_assignment_from_dict_no_locality(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'state': 'Victoria',
            'country': 'Australia',
        }
        self.address = to_python(ad)
        self.assertEqual(self.address.raw, ad['raw'])
        self.assertEqual(self.address.street_number, '')
        self.assertEqual(self.address.route, '')
        self.assertEqual(self.address.locality, None)

    def test_assignment_from_dict_only_address(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
        }
        self.address = to_python(ad)
        self.assertEqual(self.address.raw, ad['raw'])
        self.assertEqual(self.address.street_number, ad['street_number'])
        self.assertEqual(self.address.route, ad['route'])
        self.assertEqual(self.address.locality, None)

    def test_assignment_from_dict_duplicate_country_code(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'locality': 'Northcote',
            'state': 'Victoria',
            'country': 'Australia',
            'country_code': 'Australia',
        }
        self.address = to_python(ad)
        self.assertEqual(self.address.raw, ad['raw'])
        self.assertEqual(self.address.street_number, '1')
        self.assertEqual(self.address.route, 'Somewhere Street')
        self.assertEqual(self.address.locality.name, 'Northcote')
        self.assertEqual(self.address.locality.state.name, 'Victoria')
        self.assertEqual(self.address.locality.state.country.name, 'Australia')
        self.assertEqual(self.address.locality.state.country.code, '')

    def test_assignment_from_dict_duplicate_state_code(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'locality': 'Northcote',
            'state': 'Victoria',
            'state_code': 'Victoria',
            'country': 'Australia',
        }
        self.address = to_python(ad)
        self.assertEqual(self.address.raw, ad['raw'])
        self.assertEqual(self.address.street_number, '1')
        self.assertEqual(self.address.route, 'Somewhere Street')
        self.assertEqual(self.address.locality.name, 'Northcote')
        self.assertEqual(self.address.locality.state.name, 'Victoria')
        self.assertEqual(self.address.locality.state.code, '')
        self.assertEqual(self.address.locality.state.country.name, 'Australia')

    def test_assignment_from_dict_invalid_country_code(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'locality': 'Northcote',
            'state': 'Victoria',
            'country': 'Australia',
            'country_code': 'Something else',
        }
        self.assertRaises(ValueError, to_python, ad)

    def test_assignment_from_dict_invalid_state_code(self):
        ad = {
            'raw': '1 Somewhere Street, Northcote, Victoria 3070, VIC, AU',
            'street_number': '1',
            'route': 'Somewhere Street',
            'locality': 'Northcote',
            'state': 'Victoria',
            'state_code': 'Something else',
            'country': 'Australia',
        }
        self.assertRaises(ValueError, to_python, ad)

    def test_assignment_from_string(self):
        self.address = to_python(self.ad1_dict['raw'])
        self.assertEqual(self.address.raw, self.ad1_dict['raw'])

    # def test_save(self):
    #     self.test.address = self.ad1_dict
    #     self.test.save()
    #     test = self.TestModel.objects.all()[0]
    #     self.assertEqual(test.address.raw, self.ad1_dict['raw'])
    #     self.assertEqual(test.address.street_number, self.ad1_dict['street_number'])
    #     self.assertEqual(test.address.route, self.ad1_dict['route'])
    #     self.assertEqual(test.address.locality.name, self.ad1_dict['locality'])
    #     self.assertEqual(test.address.locality.postal_code, self.ad1_dict['postal_code'])
    #     self.assertEqual(test.address.locality.state.name, self.ad1_dict['state'])
    #     self.assertEqual(test.address.locality.state.code, self.ad1_dict['state_code'])
    #     self.assertEqual(test.address.locality.state.country.name, self.ad1_dict['country'])
    #     self.assertEqual(test.address.locality.state.country.code, self.ad1_dict['country_code'])
