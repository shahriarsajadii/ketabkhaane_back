import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('books', '0008_alter_book_translator'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookSeries',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=255, unique=True, verbose_name='نام مجموعه')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'مجموعه کتاب',
                'verbose_name_plural': 'مجموعه\u200cهای کتاب',
                'db_table': 'book_series',
                'ordering': ['title'],
            },
        ),
        migrations.AddField(
            model_name='book',
            name='subject',
            field=models.TextField(blank=True, default='', verbose_name='موضوع'),
        ),
        migrations.AddField(
            model_name='book',
            name='volume_number',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='شماره جلد'),
        ),
        migrations.AddField(
            model_name='book',
            name='series',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='books', to='books.bookseries', verbose_name='مجموعه'),
        ),
        migrations.AddField(
            model_name='bookcopy',
            name='is_loaned',
            field=models.BooleanField(default=False, verbose_name='امانت داده شده'),
        ),
        migrations.AddField(
            model_name='bookcopy',
            name='loaned_to',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='امانت\u200cگیرنده'),
        ),
    ]
