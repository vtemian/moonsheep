import logging
from typing import List, Type

import pbclient
from django.db import transaction
from django.utils.decorators import classproperty

from moonsheep.models import Task, Entry
from .mapper import klass_from_name
from .verifiers import MIN_CONFIDENCE, DEFAULT_DICT_VERIFIER
from .registry import register_task  # NOQA # pylint: disable=unused-import # For easier import in apps
from .settings import (
    MOONSHEEP
)

logger = logging.getLogger(__name__)


class AbstractTask(object):
    N_ANSWERS = 1

    def __init__(self, instance: Task):
        self.verified = False

        self.instance = instance
        self.id = instance.id
        self.params = instance.params
        
        # per-instance overrides
        if 'task_form' in self.params:
            self.task_form = klass_from_name(self.params.get('task_form'))
        if 'template_name' in self.params:
            self.template_name = self.params.get('template_name')

    @classproperty
    def name(cls):
        return cls.__module__ + '.' + cls.__name__

    def get_presenter(self):
        """
        Choosing how to render document to transcribe.

        The default behaviour is to check:
        1. Known url templates for YouTube, Vimeo, etc.
        2. Url file extension

        :return: {
            'template': 'presenters/fancy.html',
            'url': url,
            'other_presenter_option': 'width: 110px'
        }
        """
        # ^(https?\:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$
        # http://(www\.)?vimeo\.com/(\d+)
        url = self.instance.params['url']
        return {
            'template': 'presenters/pdf.html',
            'url': url
        }

    def verify_and_save(self, entries: List[Entry]) -> bool:
        """
        It crosschecks users' answers (entries) and if they match data is saved to structured db.

        Entries are considered cross-checked if confidence returned from the checking algorithm is greater than MIN_CONFIDENCE
        TODO otherwise...I don't know yet (will be invoked again or called "dirty data" - to be checked by moderator)
        :param entries: list containing entries
        :return: True if verified otherwise False
        """
        crosschecked, confidence = self.cross_check(entries)
        self.verified = confidence >= MIN_CONFIDENCE
        if self.verified:
            # save verified data
            with transaction.atomic():
                self.save_verified_data(crosschecked)
                # create new tasks
                self.after_save(crosschecked)

                return True
        else:
            # TODO: do something here
            return False

    def cross_check(self, entries: list) -> (dict, float):
        """
        Cross check all entries recursively
        :param entries: Entries for a given task
        :return (dict, float): (results, confidence)
        """

        verifier = DEFAULT_DICT_VERIFIER(self, '')
        return verifier(entries)

    def save_verified_data(self, verified_data: dict):
        """
        To implement in derived classes
        :param verified_data:
        :return:
        """
        raise NotImplementedError(
            "Task {}.{} should define save_verified_data method".format(self.__class__.name)
        )

    def after_save(self, verified_data):
        """
        This method is invoked right after save_verified_data.
        If user wants to do some actions afterwards, i.e. create new task, it should be done in
        method after_save in derived class.
        :type verified_data: dict
        :param verified_data: dictionary containing verified and saved fields from form
        """
        pass

    @classmethod
    def create(cls, params: dict) -> Task:
        """
        Helper method for creating a new task.

        :param task_type: Type of task you want to create
        :param params: Params to initialize the task
        :return: created task
        """

        t = Task(type=cls.name, params=params)
        t.save()

        return t

    @staticmethod
    def create_task_instance(task: Task):
        """
        Create relevant task instance.

        :param task: task description from the DB
        :return: Task object
        """

        klass = klass_from_name(task.type)
        return klass(task)

    # TODO call it from somewhere
    @staticmethod
    def verify_task(task_or_id): # TODO, simplify to one type
        if isinstance(task_or_id, int):
            task_or_id = Task.objects.get(task_or_id)
        if not isinstance(task_or_id,  Task):
            raise ValueError("task must be task_id (int) or a Task")

        # TODO find better name convention
        task_instance: Task = task_or_id
        entries = Entry.objects.filter(task=task_instance)

        task = AbstractTask.create_task_instance(task_instance)
        task.verify_and_save(entries)

    def __repr__(self):
        return "<{} id={} params={}".format(self.__class__.name, self.id, self.params)
