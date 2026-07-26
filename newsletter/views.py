from django.contrib import messages
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from uuid import uuid4

from .forms import NewsletterSignupForm
from .models import NewsletterSubscriber
from .services import enqueue_resend_welcome_email


def signup(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    form = NewsletterSignupForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please enter a valid email address.')
        return redirect(request.POST.get('next') or 'home')

    email = form.cleaned_data['email'].strip().lower()
    subscriber, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={'is_active': False},
    )

    if created:
        enqueue_resend_welcome_email(subscriber)
        messages.success(request, 'Check your inbox to confirm your subscription.')
    elif subscriber.is_active:
        messages.info(request, 'That email is already subscribed.')
    else:
        subscriber.confirmed_at = None
        subscriber.confirmation_token = uuid4()
        subscriber.save(update_fields=['confirmed_at', 'confirmation_token', 'updated_at'])
        enqueue_resend_welcome_email(subscriber)
        messages.success(request, 'Check your inbox to confirm your subscription.')

    return redirect(request.POST.get('next') or 'home')


def confirm(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)
    if subscriber.is_active and subscriber.confirmed_at:
        messages.info(request, 'Your subscription is already confirmed.')
        return redirect('home')

    subscriber.is_active = True
    subscriber.confirmed_at = subscriber.confirmed_at or timezone.now()
    subscriber.save(update_fields=['is_active', 'confirmed_at', 'updated_at'])

    messages.success(request, 'Your newsletter subscription is confirmed.')
    return redirect('home')


def unsubscribe(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, unsubscribe_token=token)
    if not subscriber.is_active:
        messages.info(request, 'You are already unsubscribed.')
        return redirect('home')

    subscriber.is_active = False
    subscriber.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, 'You have been unsubscribed from newsletter emails.')
    return redirect('home')
