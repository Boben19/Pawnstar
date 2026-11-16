from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pawn", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="supportticket",
            name="status",
            field=models.CharField(max_length=12, default="Open", choices=[(x, x) for x in ("Open", "In Progress", "Resolved", "Closed")]),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="closed_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="closed_by",
            field=models.ForeignKey(to="pawn.employee", on_delete=django.db.models.deletion.SET_NULL, null=True, blank=True, related_name="closed_support_tickets"),
        ),
        migrations.AddField(
            model_name="supportticket",
            name="closed_by_name",
            field=models.CharField(max_length=120, blank=True),
        ),
    ]
