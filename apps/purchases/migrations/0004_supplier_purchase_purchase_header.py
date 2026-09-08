import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchases", "0003_alter_purchase_discount"),
    ]

    operations = [
        migrations.CreateModel(
            name="Supplier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150, verbose_name="nombre")),
                ("tax_id", models.CharField(blank=True, max_length=20, verbose_name="NIT")),
                ("phone", models.CharField(blank=True, max_length=20, verbose_name="teléfono")),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("address", models.TextField(blank=True, verbose_name="dirección")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="users.user")),
            ],
            options={
                "verbose_name": "proveedor",
                "verbose_name_plural": "proveedores",
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="purchase",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=50, verbose_name="número de factura"),
        ),
        migrations.AddField(
            model_name="purchase",
            name="purchase_date",
            field=models.DateField(default=django.utils.timezone.localdate, verbose_name="fecha de compra"),
        ),
        migrations.AddField(
            model_name="purchase",
            name="supplier",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="purchases", to="purchases.supplier", verbose_name="proveedor"),
        ),
    ]