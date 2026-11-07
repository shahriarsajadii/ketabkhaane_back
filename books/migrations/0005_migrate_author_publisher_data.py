# مرحله‌ی ۲ از ۳: انتقال نام‌های متنی قدیمی به رکوردهای ناشر/نویسنده

from django.db import migrations


def _clean(value):
    return " ".join((value or "").split())


def forwards(apps, schema_editor):
    Book = apps.get_model("books", "Book")
    Author = apps.get_model("authors", "Author")
    Publisher = apps.get_model("publishers", "Publisher")

    publishers = {p.name.lower(): p for p in Publisher.objects.all()}
    authors = {a.name.lower(): a for a in Author.objects.all()}

    for book in Book.objects.all().iterator():
        changed = False

        name = _clean(book.publisher_old)[:255]
        if name:
            publisher = publishers.get(name.lower())
            if publisher is None:
                publisher = Publisher.objects.create(name=name)
                publishers[name.lower()] = publisher
            book.publisher_id = publisher.pk
            changed = True

        name = _clean(book.author)[:255]
        if name:
            author = authors.get(name.lower())
            if author is None:
                author = Author.objects.create(name=name)
                authors[name.lower()] = author
            book.authors.add(author)

        if changed:
            book.save(update_fields=["publisher"])


def backwards(apps, schema_editor):
    Book = apps.get_model("books", "Book")
    for book in Book.objects.all().iterator():
        book.author = "، ".join(a.name for a in book.authors.all())[:255]
        book.publisher_old = book.publisher.name if book.publisher_id else ""
        book.save(update_fields=["author", "publisher_old"])


class Migration(migrations.Migration):

    dependencies = [
        ('books', '0004_book_authors_book_publisher_fk'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
