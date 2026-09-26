from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.template.response import TemplateResponse
from django.urls import reverse
from .models import NewsletterCampaign, NewsletterSubscriber
from .services import get_campaign_recipients, send_newsletter_campaign


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('email',)
    ordering = ('-created_at',)


@admin.register(NewsletterCampaign)
class NewsletterCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'recipient_count', 'sent_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject',)
    ordering = ('-created_at',)
    fields = (
        'subject', 'text_body',
        'status', 'recipient_count', 'error_message', 'sent_at', 'created_at', 'updated_at',
    )
    readonly_fields = ('status', 'recipient_count', 'error_message', 'sent_at', 'created_at', 'updated_at')
    actions = ['send_now']

    @admin.action(description='Send now to all confirmed subscribers')
    def send_now(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, 'Select exactly one campaign to send.', level=messages.ERROR)
            return

        campaign = queryset.first()

        if 'confirm_send' not in request.POST:
            return TemplateResponse(
                request,
                'admin/newsletter/confirm_send.html',
                {
                    **self.admin_site.each_context(request),
                    'opts': self.model._meta,
                    'campaign': campaign,
                    'recipient_count': get_campaign_recipients().count(),
                    'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                    'cancel_url': reverse('admin:newsletter_newslettercampaign_changelist'),
                },
            )

        try:
            count = send_newsletter_campaign(campaign)
        except RuntimeError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return

        self.message_user(request, f'Sent "{campaign.subject}" to {count} subscriber(s).')
