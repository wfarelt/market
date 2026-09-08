from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_product_cost_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(blank=True, upload_to="products/", verbose_name="imagen"),
        ),
        migrations.AddField(
            model_name="product",
            name="product_type",
            field=models.CharField(choices=[("RAW_MATERIAL", "Materia prima"), ("FINISHED_GOOD", "Producto final")], default="FINISHED_GOOD", max_length=20, verbose_name="tipo de producto"),
        ),
    ]