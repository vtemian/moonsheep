import io

from rest_framework import routers, serializers, viewsets
from django.apps import apps

from moonsheep.exporters.exporters import Exporter


class AppApi(Exporter):
    """
    AppApi generates an API for a given project

    AppApi should be registered on project's urls as follows `path('api/opora/', include(AppApi('opora').urls)),`")
    """
    def __init__(self, app_label):
        super().__init__(app_label)

        self.router = routers.DefaultRouter()

        # Iterate through all defined models in the app and create endpoints for them
        for slug, model_cls, serializer_cls, queryset in self.models():
            viewset_cls = type(model_cls.__name__ + "ViewSetDefault", (viewsets.ModelViewSet,), dict(
                queryset=queryset,
                serializer_class=serializer_cls
            ))

            # Register endpoints
            self.router.register(slug, viewset_cls)

    @property
    def urls(self):
        """
        Register AppApi on urls as follow using your app_label:
        path('api/opora/', include(AppApi('opora').urls)),

        :return:
        """
        return self.router.urls, 'api-' + self.app_label
