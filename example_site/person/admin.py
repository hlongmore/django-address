from django.contrib import admin
from dj_address.models import AddressField
from dj_address.forms import AddressWidget
from .models import Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'address',
    )

    formfield_overrides = {
        AddressField: {
            'widget': AddressWidget(
                attrs={
                    'style': 'width: 300px;'
                }
            )
        }
    }
