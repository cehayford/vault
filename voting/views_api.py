from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .views import _elections_for_user
from .serializers import ElectionListSerializer, ElectionDetailSerializer


class ElectionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return _elections_for_user(self.request)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ElectionDetailSerializer
        return ElectionListSerializer
