from django.test import TestCase as DjangoTestCase, Client, override_settings
from django.http.request import QueryDict
from unittest import TestCase as UnitTestCase
from unittest.mock import Mock, MagicMock, patch, sentinel

from moonsheep.tasks import AbstractTask
from moonsheep.exceptions import PresenterNotDefined
from moonsheep.views import unpack_post
from moonsheep.tests import DummyTask
from moonsheep.verifiers import EqualsVerifier, UnorderedSetVerifier

import json


class PresenterTests(UnitTestCase):

    def get_presenter(self, url):
        """
        Choosing how to render document to transcribe.

        The default behaviour is to check:
        1. Known url templates for YouTube, Vimeo, etc.
        2. Url file extension
        """

    def _test_presenter(self, url, template, url_out=None):
        t = AbstractTask(url)
        p = t.get_presenter()

        if url_out is None:
            url_out = url

        self.assertDictEqual(p, {
            'template': 'presenters/{}.html'.format(template),
            'url': url_out
        })

    def test_youtube(self):
        self._test_presenter('https://www.youtube.com/watch?v=qEI1_oGPQr0', 'youtube')

    def test_youtube_not_valid(self):
        t = AbstractTask('https://www.youtube.com/')

        with self.assertRaises(PresenterNotDefined):
            t.get_presenter()

    def test_vimeo(self):
        self._test_presenter('https://vimeo.com/201762745', 'vimeo')

    def test_vimeo_not_valid(self):
        t = AbstractTask('https://vimeo.com/')

        with self.assertRaises(PresenterNotDefined):
            t.get_presenter()

    def test_extension_pdf(self):
        self._test_presenter('http://domain.pl/document.pdf', 'pdf')

    def test_extension_png(self):
        self._test_presenter('http://domain.pl/document.png', 'image')

    def test_extension_jpg(self):
        self._test_presenter('http://domain.pl/document.jpg', 'image')

    def test_extension_jpeg(self):
        self._test_presenter('http://domain.pl/document.jpeg', 'image')

    def test_missing_presenter(self):
        t = AbstractTask('http://domain.pl/document.whatthehell')

        with self.assertRaises(PresenterNotDefined):
            t.get_presenter()

# TODO test error handling for Tasks with no form and no template


class UnpackPostTest(UnitTestCase):
    """
    It tests moonsheep.views.unpack_post function.

    Unpack items in POST fields that have multiple occurences.

    It handles:
    - multiple fields without brackets, ie. field
    - multiple fields PHP5 style, ie. field[]
    - objects, ie. obj[field1]=val1 obj[field2]=val2
    - multiple rows of several fields, ie. row[0][field1], row[1][field1]
    - hierarchily nested multiples, ie. row[0][entry_id], row[0][entry_options][]

    :param: post QueryDict
    :return: list or dict
    """

    def test_querydict_single(self):
        post = QueryDict('field=val1')
        self.assertEqual(post['field'], 'val1')
        self.assertEqual(post.getlist('field'), ['val1'])
        self.assertDictEqual(post, {
            'field': ['val1']
        })

    def test_querydict_multiple(self):
        post = QueryDict('field=val1&field=val2')

        # simple __get_item__ returns last value
        self.assertEqual(post['field'], 'val2')

        # to get all values one have to use getlist
        self.assertEqual(post.getlist('field'), ['val1', 'val2'])

        # equals takes into account multiple values
        self.assertDictEqual(post, {
            'field': ['val1', 'val2']
        })

        # but QuueryDict.dict() don't (it just return the last value)
        self.assertDictEqual(post.dict(), {
            'field': 'val2'
        })

    def test_multiple_wo_brackets(self):
        post = QueryDict('field=val1&field=val2')
        self.assertDictEqual(unpack_post(post), {
            'field': ['val1', 'val2']
        })

    def test_multiple_with_brackets(self):
        post = QueryDict('field[]=val1&field[]=val2')
        self.assertDictEqual(unpack_post(post), {
            'field': ['val1', 'val2']
        })

    def test_single_wo_brackets(self):
        post = QueryDict('field=val1')
        self.assertDictEqual(unpack_post(post), {
            'field': 'val1'
        })

    def test_single_with_brackets(self):
        """
        Where we assume that the developer wanted list
        """
        post = QueryDict('field[]=val1')
        self.assertDictEqual(unpack_post(post), {
            'field': ['val1']
        })

    def test_object(self):
        post = QueryDict('obj[field1]=val1&obj[field2]=val2')
        self.assertDictEqual(unpack_post(post), {
            'obj': {
                'field1': 'val1',
                'field2': 'val2'
            }
        })

    def test_rows(self):
        post = QueryDict('row[0][field1]=val1&row[0][field2]=val2&row[1][field1]=val3')
        self.assertDictEqual(unpack_post(post), {
            'row': [
                {'field1': 'val1', 'field2': 'val2'},
                {'field1': 'val3'}
            ]
        })

    def test_rows_alpha_index(self):
        """
        TODO this test is unstable (once fails, once not)
        :return:
        """
        post = QueryDict('row[0][fld]=0&row[bla][fld]=bla')
        with self.assertRaises(ValueError):
            unpack_post(post)

    def test_rows_missing_index(self):
        """
        For now, we don't throw errors.. Should we?
        """
        post = QueryDict('row[0][fld]=0&row[2][fld]=2')
        self.assertDictEqual(unpack_post(post), {
            'row': [
                {'fld': '0'},
                {'fld': '2'}
            ]
        })

    def test_rows_inverse_order(self):
        post = QueryDict('row[1][field1]=val3&row[0][field1]=val1&row[0][field2]=val2')
        self.assertDictEqual(unpack_post(post), {
            'row': [
                {'field1': 'val1', 'field2': 'val2'},
                {'field1': 'val3'}
            ]
        })

    def test_rows_inverse_order_numcomparison(self):
        """
        to check that 1, 10, 2 are sorted numerically and not alphabetically
        """
        post = QueryDict('&'.join(['row[{}][fld]={}'.format(i, i) for i in range(11, -1, -1)]))
        self.assertDictEqual(unpack_post(post), {
            'row': [
                {'fld': '0'},
                {'fld': '1'},
                {'fld': '2'},
                {'fld': '3'},
                {'fld': '4'},
                {'fld': '5'},
                {'fld': '6'},
                {'fld': '7'},
                {'fld': '8'},
                {'fld': '9'},
                {'fld': '10'},
                {'fld': '11'}
            ]
        })
        pass

    def test_nested_rows_not_numbered(self):
        post = QueryDict('row[0][entry_id]=val1&row[0][entry_options][]=val2&row[0][entry_options][]=val3')
        self.assertDictEqual(unpack_post(post), {
            'row': [{
                'entry_id': 'val1',
                'entry_options': ['val2', 'val3']
            }]
        })

    def test_nested_rows_numbered(self):
        """
        TODO fails sometimes, sometimes work
        - {'row': [{'entry_id': 'val1', 'entry_options': {'0': 'val2', '1': 'val3'}}]}
?                                                ^^^^^^        -----      ^

+ {'row': [{'entry_id': 'val1', 'entry_options': ['val2', 'val3']}]}
?
        :return:
        """
        post = QueryDict('row[0][entry_id]=val1&row[0][entry_options][0]=val2&row[0][entry_options][1]=val3')
        self.assertDictEqual(unpack_post(post), {
            'row': [{
                'entry_id': 'val1',
                'entry_options': ['val2', 'val3']
            }]
        })


@override_settings(ROOT_URLCONF='moonsheep.urls')
class TaskProcessingTests(DjangoTestCase):

    @patch('moonsheep.tasks.AbstractTask.verify_task')
    def test_webhook_exists(self, verify_task_mock: MagicMock):
        client = Client()
        response = client.get('/webhooks/task-run/')

        self.assertEqual(response.status_code, 200)
        verify_task_mock.assert_not_called()

    @patch('moonsheep.tasks.AbstractTask.verify_task')
    def test_webhook_receives(self, verify_task_mock: MagicMock):
        client = Client()
        data = {
            'event': 'task_completed',
            'project_id': "PROJECT_ID",
            'task_id': "TASK_ID",
        }
        response = client.post('/webhooks/task-run/', json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        verify_task_mock.assert_called_with("PROJECT_ID", "TASK_ID")

    def test_webhook_receives_missing_data(self):
        client = Client()
        data = {
            'event': 'task_completed',
        }
        response = client.post('/webhooks/task-run/', json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 400)

    def test_webhook_unrecognized_event(self):
        client = Client()
        data = {
            'event': 'unknown_event',
        }
        response = client.post('/webhooks/task-run/', json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 400)

    def test_webhook_no_payload(self):
        client = Client()
        response = client.post('/webhooks/task-run/')

        self.assertEqual(response.status_code, 400)

    @patch('moonsheep.tasks.AbstractTask.after_save')
    @patch('moonsheep.tasks.AbstractTask.save_verified_data')
    def test_flow_of_verified(self, save_verified_data_mock, after_save_mock):
        verified_data = {'fld': 'val1'}

        task = AbstractTask(info={'url': 'https://bla.pl'})

        # TODO test verification on one input
        task.verify_and_save([verified_data, verified_data])

        save_verified_data_mock.assert_called_with(verified_data)
        after_save_mock.assert_called_with(verified_data)

    @patch('moonsheep.tasks.AbstractTask.after_save')
    @patch('moonsheep.tasks.AbstractTask.save_verified_data')
    def test_flow_one_input(self, save_verified_data_mock, after_save_mock):
        """
        One input shouldn't be enough for verification to run successful
        In future this may be extended to set a limit
        :return:
        """
        verified_data = {'fld': 'val1'}

        task = AbstractTask(info={'url': 'https://bla.pl'})

        task.verify_and_save([verified_data])

        save_verified_data_mock.assert_not_called_with(verified_data)
        after_save_mock.assert_not_called_with(verified_data)

    def test_flow_of_unverified(self):
        """
        TODO
        :return:
        """
        pass

    def test_create_task_instance(self):
        task = AbstractTask.create_task_instance('moonsheep.tests.DummyTask', info={'url': 'https://bla.pl'})
        self.assertEquals(task.__class__, DummyTask)

    @patch('moonsheep.verifiers.EqualsVerifier.__call__')
    def test_verification_default_equals_mock(self, equals_mock: MagicMock):
        verified_dict_data = {'fld': 'val1'}
        task = AbstractTask(info={'url': 'https://bla.pl'})

        equals_mock.return_value = (1, verified_dict_data)
        
        task.cross_check([verified_dict_data, verified_dict_data])
        equals_mock.assert_called_with([verified_dict_data, verified_dict_data])

    def test_verification_default_equals_true(self):
        verified_dict_data = {'fld': 'val1'}
        task = AbstractTask(info={'url': 'https://bla.pl'})

        (confidence, result) = task.cross_check([verified_dict_data, verified_dict_data])
        self.assertEquals(result, verified_dict_data)

    def test_verification_default_equals_false(self):
        task = AbstractTask(info={'url': 'https://bla.pl'})

        (confidence, result) = task.cross_check([{'fld': 'val1'}, {'fld': 'whatever'}])
        self.assertEquals(confidence, 0)
        self.assertEquals(result, None)

    @patch('moonsheep.verifiers.UnorderedSetVerifier.__call__')
    def test_verification_default_unordered_set_mock(self, unordered_set_mock: MagicMock):
        verified_list_data = [1, 2, 3]
        task = AbstractTask(info={'url': 'https://bla.pl'})

        task.cross_check([verified_list_data, verified_list_data])
        unordered_set_mock.assert_called_with([verified_list_data, verified_list_data])

    def test_verification_default_unordered_set_true(self):
        verified_list_data = [1, 2, 3]
        task = AbstractTask(info={'url': 'https://bla.pl'})

        (confidence, result) = task.cross_check([verified_list_data, verified_list_data])
        self.assertEquals(result, verified_list_data)

    def test_verification_default_unordered_set_false(self):
        task = AbstractTask(info={'url': 'https://bla.pl'})

        (confidence, result) = task.cross_check([[1, 2, 3], [7, 8]])
        self.assertEquals(confidence, 0)
        self.assertEquals(result, None)
