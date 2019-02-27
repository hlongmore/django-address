# django-address

## Disclaimer

These instructions are a little shabby, I haven't had a whole lot of time to
devote to explaining things thoroughly. If you're interested in using this
but are having trouble getting it setup please feel free to email me at
furious.luke@gmail.com, I'll assist as best I can and update the instructions
in the process. Cheers!

Also, *there will be bugs*, please let me know of any issues and I'll do my
best to fix them.

## Installation

Previously a patch for Django was required to make this app work, but as
of 1.7 the patch is no longer needed. Installation is now done as per
usual. The package is installed with:

```bash
python setup.py install
```

Then, add `address` to your `INSTALLED_APPS` list in `settings.py`:

```python
INSTALLED_APPS = (
    ...
    dj_address,
)
```

You wil need to add your Google Maps API key to `settings.py` too:
```
GOOGLE_API_KEY = 'AIzaSyD--your-google-maps-key-SjQBE'
```

##### Additional Settings

The Google Geocoding API can handle subpremise where the Autocomplete API can't. If
a subpremise is specified, the Geocoding API will be consulted. If it can't find an
exact match, but it can find the right street address, there are two possible ways
to proceed. The first is to retry the Geocoding API call, replacing the returned 
subpremise with the subpremise from the raw data. The other is to just assume the
data is correct if the correct street number was returned and the lat/long are
defined, then change the subpremise to the user-specified value. These options
are controlled by the settings:

```python
# Deal with ambiguity for subpremise
DJ_ADDRESS_SUBPREMISE_GEOCODE_RETRY_WITH_REPLACE = False
DJ_ADDRESS_SUBPREMISE_REPLACE_ONLY = True
```

The reason for allowing the choice is that retrying is currently unreliable. For
an address that is formatted correctly and not missing data, the right data is 
returned; however for that same address but with no commas, the correct street
address is returned, but with a different subpremise. Retrying using the intended
subpremise substituted into the returned formatted address (making the address 
identical to the one used that gave the desired results) just gives the first
result again.

Sometimes the subpremise is not returned, perhaps because the country was included;
in this case it may be best to ignore the missing subpremise, acting as if it had
been returned. This is controlled by:

```python
DJ_ADDRESS_IGNORE_MISSING_SUBPREMISE = True
```

For concrete examples of these inconsistencies, see the following unit tests:

```python
test_substitute_subpremise_for_partial_match
test_retry_using_formatted_for_partial_match
test_substitute_subpremise_raw_includes_country
test_retry_using_formatted_raw_includes_country
```


## The Model

The rationale behind the model structure is centered on trying to make
it easy to enter addresses that may be poorly defined. The model field included
uses Google Maps API v3 (via the nicely done [geocomplete jquery plugin](http://ubilabs.github.io/geocomplete/)) to
determine a proper address where possible. However if this isn't possible the
raw address is used and the user is responsible for breaking the address down
into components.

It's currently assumed any address is represent-able using four components:
country, state, locality and street address. In addition, country code, state
code and postal code may be stored, if they exist.

There are four Django models used:

```
  Country
    name
    code

  State
    name
    code
    country -> Country

  Locality
    name
    postal_code
    state -> State

  Address
    raw
    street_number
    route
    subpremise
    locality -> Locality
```

## Address Field

To simplify storage and access of addresses, a subclass of `ForeignKey` named
`AddressField` has been created. It provides an easy method for setting new
addresses.

### Creation

It can be created using the same optional arguments as a ForeignKey field.
For example:

```python
  from address.models import AddressField

  class MyModel(models.Model):
    address1 = AddressField()
    address2 = AddressField(related_name='+', blank=True, null=True)
```

### Setting Values

Values can be set either by assigning an Address object:

```python
  addr = Address(...)
  addr.save()
  obj.address = addr
```

Or by supplying a dictionary of address components:

```python
  obj.address = {'street_number': '1', route='Somewhere Ave', ...}
```

The structure of the address components is as follows:

```python
  {
    'raw': '1 Somewhere Ave, Northcote, VIC 3070, AU',
    'street_number': '1',
    'route': 'Somewhere Ave',
    'subpremise': '300',
    'locality': 'Northcote',
    'postal_code': '3070',
    'state': 'Victoria',
    'state_code': 'VIC',
    'country': 'Australia',
    'country_code': 'AU'
  }
```

All except the `raw` field can be omitted. In addition, a raw address may
be set directly:

```python
obj.address = 'Out the back of 1 Somewhere Ave, Northcote, Australia'
```

### Getting Values

When accessed, the address field simply returns an Address object. This way
all components may be accessed naturally through the object. For example::

```python
  route = obj.address.route
  state_name = obj.address.locality.state.name
```

## Forms

Included is a form field for simplifying address entry. A Google maps
auto-complete is performed in the browser and passed to the view. If
the lookup fails the raw entered value is used.

TODO: Talk about this more.

## Partial Example

The model:

```python
from address.models import AddressField

class Person(models.Model):
  address = AddressField()
```

The form:

```
from address.forms import AddressField

class PersonForm(forms.Form):
  address = AddressField()
```

The template:

```html
<head>
{{ form.media }} <!-- needed for JS/GoogleMaps lookup -->
</head>
<body>
  {{ form }}
</body>
```
