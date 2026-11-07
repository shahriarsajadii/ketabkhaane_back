# مرحله‌ی ۳ از ۳: حذف فیلدهای متنی قدیمی

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0005_migrate_author_publisher_data'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='book',
            name='author',
        ),
        migrations.RemoveField(
            model_name='book',
            name='publisher_old',
        ),
    ]
