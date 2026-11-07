# مرحله‌ی ۱ از ۳: ساخت فیلدهای جدید (ناشر و نویسنده‌ها) کنار فیلدهای متنی قدیمی

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authors', '0001_initial'),
        ('publishers', '0001_initial'),
        ('books', '0003_book_circulation_book_dewey_classification_and_more'),
    ]

    operations = [
        # اسم «publisher» باید آزاد شود تا ForeignKey جدید با همین اسم ساخته شود
        migrations.RenameField(
            model_name='book',
            old_name='publisher',
            new_name='publisher_old',
        ),
        migrations.AddField(
            model_name='book',
            name='publisher',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='books', to='publishers.publisher', verbose_name='ناشر'),
        ),
        migrations.AddField(
            model_name='book',
            name='authors',
            field=models.ManyToManyField(blank=True, related_name='books', to='authors.author', verbose_name='نویسنده\u200cها'),
        ),
    ]
