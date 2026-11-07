from django.urls import path

from .views import CategoryListCreate, CategoryRetrieveUpdateDelete

urlpatterns = [
    path("", CategoryListCreate.as_view(), name="categories.list-create"),
    path("detail/<int:param>/", CategoryRetrieveUpdateDelete.as_view(), name="categories.retrieve-update-delete"),
]
