from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("settings_app", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="companysettings",
            name="enable_card_payment",
            field=models.BooleanField(default=True, verbose_name="tarjeta"),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="enable_cash_payment",
            field=models.BooleanField(default=True, verbose_name="efectivo"),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="enable_credit_payment",
            field=models.BooleanField(default=True, verbose_name="crédito"),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="enable_qr_payment",
            field=models.BooleanField(default=True, verbose_name="QR"),
        ),
        migrations.AddField(
            model_name="companysettings",
            name="enable_transfer_payment",
            field=models.BooleanField(default=True, verbose_name="transferencia"),
        ),
    ]