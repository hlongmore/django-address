# -*- coding: utf-8 -*-

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dj_address', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='locality',
            unique_together={('name', 'postal_code', 'state')},
        ),
    ]
