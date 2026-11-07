from django.urls import path

from .views import PublisherImage, PublisherListCreate, PublisherRetrieveUpdateDelete

urlpatterns = [
    path("", PublisherListCreate.as_view(), name="publishers.list-create"),
    path("detail/<int:param>/", PublisherRetrieveUpdateDelete.as_view(), name="publishers.retrieve-update-delete"),
    path("<int:param>/image/", PublisherImage.as_view(), name="publishers.image"),
]
