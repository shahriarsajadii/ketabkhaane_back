from django.urls import path

from .views import AuthorImage, AuthorListCreate, AuthorRetrieveUpdateDelete

urlpatterns = [
    path("", AuthorListCreate.as_view(), name="authors.list-create"),
    path("detail/<int:param>/", AuthorRetrieveUpdateDelete.as_view(), name="authors.retrieve-update-delete"),
    path("<int:param>/image/", AuthorImage.as_view(), name="authors.image"),
]
