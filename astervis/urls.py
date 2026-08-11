"""
URL configuration for astervis project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.models import User
from django.urls import include, path
from os import environ
from . import views

urlpatterns = [
    path(f'', views.home, name="home"),
    path(f'search/', views.search, name="search"),
    path(f'visualizer/', include("visualizer.urls")),
    path(f'admin/', admin.site.urls),
] + static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS)

# Apparently here is the "reccomended" position for code that I want to run on startup
# If a name and password are provided, and there are no pre-existing superusers, create the default one.
name = environ.get("DJANGO_SUPERUSER_NAME","")
pword = environ.get("DJANGO_SUPERUSER_PWORD","")
if name and pword and not User.objects.all():
    User.objects.create_superuser(name, None, pword).save()