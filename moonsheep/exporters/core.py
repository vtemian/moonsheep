import io
from abc import ABC, abstractmethod
from typing import Union

import pandas as pd
from django.apps import apps
from rest_framework import serializers

from moonsheep.plugins import Interface


class Exporter(Interface):
    @abstractmethod
    def export(self, output: Union[io.IOBase, str], **options):
        pass

    @classmethod
    def implementations(cls):
        impls = super().implementations()
        del impls['appapi']
        return impls

    def __init__(self, app_label):
        self.app_label = app_label
        # TODO default label
        # TODO what if label does not exist

    def models(self):
        """
        Returns generator that retrieves all data and meta information needed to export data.

        Usage:
        for slug, model_cls, serializer_cls, queryset in self.models():
            serializer = serializer_cls(queryset, many=True)
            data = serializer.data
            # export data

        :return:
        """
        for slug, model_cls in apps.get_app_config(self.app_label).models.items():
            class Meta:
                model = model_cls
                fields = '__all__'  # TODO by default drop some fields such as progress on Document

            serializer_cls = type(model_cls.__name__ + "SeralizerDefault", (serializers.ModelSerializer,), dict(
                Meta=Meta
            ))

            # Projects can override default queryset adding 'exported' filter to choose which objects to export
            if hasattr(model_cls.objects, 'exported'):
                queryset = model_cls.objects.exported()
            else:
                queryset = model_cls.objects.all()

            yield slug, model_cls, serializer_cls, queryset.order_by('pk')


class PandasExporter(Exporter, ABC):
    """
    Base class to write exporters building on Pandas library

    Pandas supports: xlsx, csv, json, hdfs, sql, sas, stata, google big query
    """

    def data_frames(self):
        for slug, model_cls, serializer_cls, queryset in self.models():
            serializer = serializer_cls(queryset, many=True)
            data = serializer.data

            yield slug, pd.DataFrame(data)
