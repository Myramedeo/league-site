from rest_framework.viewsets import ReadOnlyModelViewSet
from .models import Announcement
from .serializers import AnnouncementSerializer


class AnnouncementViewSet(ReadOnlyModelViewSet):
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        return Announcement.objects.filter(active=True)
