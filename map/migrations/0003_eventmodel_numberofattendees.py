# Generated by Django 3.1.5 on 2021-04-14 03:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('map', '0002_auto_20210413_1835'),
    ]

    operations = [
        migrations.AddField(
            model_name='eventmodel',
            name='numberOfAttendees',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
