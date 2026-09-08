from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0002_companysettings_payment_methods"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companysettings",
            name="address",
            field=models.TextField(blank=True, verbose_name="dirección"),
        ),
        migrations.AlterField(
            model_name="companysettings",
            name="phone",
            field=models.CharField(blank=True, max_length=20, verbose_name="teléfono"),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="logo",
            field=models.ImageField(blank=True, upload_to="company/", verbose_name="logo"),
        ),
    ]