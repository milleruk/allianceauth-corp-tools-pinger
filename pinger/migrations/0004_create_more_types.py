# Generated by Aaron on 2021-11-10

from django.db import migrations


def add_ping_types(apps, schema_editor):
    PingType = apps.get_model('pinger', 'PingType')

    #StructureLostShields
    PingType.objects.create(name="Structures: Structure Lost Shields",
        class_tag="StructureLostShields")
    #StructureLostArmor
    PingType.objects.create(name="Structures: Structure Lost Armor",
        class_tag="StructureLostArmor")
    #StructureUnderAttack
    PingType.objects.create(name="Structures: Structure Under Attack",
        class_tag="StructureUnderAttack")
    #SovStructureReinforced
    PingType.objects.create(name="SOV: SOV Structure Reinforced",
        class_tag="SovStructureReinforced")
    #EntosisCaptureStarted
    PingType.objects.create(name="SOV: Entosis Started",
        class_tag="EntosisCaptureStarted")
    #OwnershipTransferred
    PingType.objects.create(name="Admin: Structure Transfer",
        class_tag="OwnershipTransferred")


class Migration(migrations.Migration):

    dependencies = [
        ('pinger', '0003_auto_20211108_0024'),
    ]

    operations = [
        migrations.RunPython(add_ping_types)
    ]
