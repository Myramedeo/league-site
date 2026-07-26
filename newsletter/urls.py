from django.urls import path

from .views import confirm, signup, unsubscribe

urlpatterns = [
    path('signup/', signup, name='newsletter_signup'),
    path('confirm/<uuid:token>/', confirm, name='newsletter_confirm'),
    path('unsubscribe/<uuid:token>/', unsubscribe, name='newsletter_unsubscribe'),
]
