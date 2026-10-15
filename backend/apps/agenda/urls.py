from django.urls import path

from .views import AgendaView

urlpatterns = [path("agenda/", AgendaView.as_view(), name="agenda")]
