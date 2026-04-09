# accounts/urls.py
from django.urls import path

from .views import SignUpView

urlpatterns = [
    path("add_user/", SignUpView.as_view(), name="signup"),
]