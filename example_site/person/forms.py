from django import forms
from dj_address.forms import AddressField


class PersonForm(forms.Form):
    address = AddressField()
