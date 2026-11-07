from django.contrib import admin

from .models import Book, BookCopy


class BookCopyInline(admin.TabularInline):
    model = BookCopy
    extra = 1


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "translator", "publisher", "created_at")
    search_fields = ("title", "authors__name", "translator", "publisher__name", "isbn")
    list_filter = ("categories",)
    autocomplete_fields = ("authors", "publisher")
    inlines = [BookCopyInline]
