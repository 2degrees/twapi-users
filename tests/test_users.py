##############################################################################
#
# Copyright (c) 2015, 2degrees Limited.
# All Rights Reserved.
#
# This file is part of twapi-users
# <https://github.com/2degrees/twapi-users>, which is subject to the
# provisions of the BSD at
# <http://dev.2degreesnetwork.com/p/2degrees-license.html>. A copy of the
# license should accompany this distribution. THIS SOFTWARE IS PROVIDED "AS IS"
# AND ANY AND ALL EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST
# INFRINGEMENT, AND FITNESS FOR A PARTICULAR PURPOSE.
#
##############################################################################

from abc import ABCMeta
from abc import abstractmethod
from abc import abstractproperty
from inspect import isgenerator
from itertools import islice

from nose.tools import eq_
from twapi_connection.testing import MockConnection
from twapi_connection.testing import SuccessfulAPICall

from twapi_users import BATCH_RETRIEVAL_SIZE_LIMIT
from twapi_users import Group
from twapi_users import User
from twapi_users import get_deleted_users
from twapi_users import get_group_members
from twapi_users import get_groups
from twapi_users import get_users


class _ObjectsRetrievalTestCase(metaclass=ABCMeta):

    _DATA_RETRIEVER = abstractproperty()

    _SIMULATOR = abstractproperty()

    def test_no_data(self):
        self._test_retrieved_objects(0)

    def test_not_exceeding_pagination_size(self):
        self._test_retrieved_objects(BATCH_RETRIEVAL_SIZE_LIMIT - 1)

    def test_exceeding_pagination_size(self):
        self._test_retrieved_objects(BATCH_RETRIEVAL_SIZE_LIMIT + 1)

    def _test_retrieved_objects(self, count):
        objects = self._generate_deserialized_objects(count)
        simulator = self._make_simulator(objects)
        with MockConnection(simulator) as connection:
            data = self._retrieve_data(connection)
            retrieved_objects = list(data)
        eq_(objects, retrieved_objects)

    def _retrieve_data(self, connection):
        return self._DATA_RETRIEVER(connection)

    def _make_simulator(self, objects):
        return self._SIMULATOR(objects)

    @abstractmethod
    def _generate_deserialized_objects(self, count):
        pass


class _PaginatedObjectsRetriever(metaclass=ABCMeta):

    _api_endpoint_url = abstractproperty()

    def __init__(self, objects):
        super(_PaginatedObjectsRetriever, self).__init__()
        self._objects_by_page = _paginate(objects, BATCH_RETRIEVAL_SIZE_LIMIT)
        self._objects_count = len(objects)

    def __call__(self):
        api_calls = []

        if self._objects_by_page:
            first_page_objects = self._objects_by_page[0]
        else:
            first_page_objects = []

        first_page_api_call = self._get_api_call_for_page(first_page_objects)
        api_calls.append(first_page_api_call)

        subsequent_pages_objects = self._objects_by_page[1:]
        for page_objects in subsequent_pages_objects:
            api_call = self._get_api_call_for_page(page_objects)
            api_calls.append(api_call)

        return api_calls

    def _get_api_call_for_page(self, page_objects):
        page_number = self._get_current_objects_page_number(page_objects)
        response_body_deserialization = \
            self._get_response_body_deserialization(page_objects)
        api_call = SuccessfulAPICall(
            self._get_page_url(page_number),
            'GET',
            response_body_deserialization=response_body_deserialization,
            )
        return api_call

    def _get_response_body_deserialization(self, page_objects):
        page_number = self._get_current_objects_page_number(page_objects)
        pages_count = len(self._objects_by_page)
        page_has_successors = page_number < pages_count
        if page_has_successors:
            next_page_url = self._get_page_url(page_number + 1)
        else:
            next_page_url = None

        page_objects_data = self._get_objects_data(page_objects)
        response_body_deserialization = {
            'count': self._objects_count,
            'next': next_page_url,
            'results': page_objects_data,
            }
        return response_body_deserialization

    def _get_page_url(self, page_number):
        page_url = self._api_endpoint_url
        if 1 < page_number:
            page_url += '?page={}'.format(page_number)
        return page_url

    def _get_current_objects_page_number(self, page_objects):
        if self._objects_by_page:
            page_number = self._objects_by_page.index(page_objects) + 1
        else:
            page_number = 1
        return page_number

    def _get_objects_data(self, objects):
        return objects


class _PaginatedObjectsRetrieverWithUpdates(_PaginatedObjectsRetriever):

    def __init__(
        self,
        objects,
        output_future_updates_url,
        input_future_updates_url=None,
        ):
        super(_PaginatedObjectsRetrieverWithUpdates, self).__init__(objects)

        self.output_future_updates_url = output_future_updates_url
        self.input_future_updates_url = input_future_updates_url

    def _get_response_body_deserialization(self, page_objects):
        response_body_deserialization = \
            super(_PaginatedObjectsRetrieverWithUpdates, self) \
                ._get_response_body_deserialization(page_objects)

        response_body_deserialization['future_updates'] = \
            self.output_future_updates_url
        return response_body_deserialization


def _paginate(iterable, page_size):
    return list(_ipaginate(iterable, page_size))


def _ipaginate(iterable, page_size):
    if not isgenerator(iterable):
        iterable = iter(iterable)

    next_page_iterable = _get_next_page_iterable_as_list(iterable, page_size)
    while next_page_iterable:
        yield next_page_iterable

        next_page_iterable = \
            _get_next_page_iterable_as_list(iterable, page_size)


def _get_next_page_iterable_as_list(iterable, page_size):
    next_page_iterable = list(islice(iterable, page_size))
    return next_page_iterable


class _GetUsers(_PaginatedObjectsRetriever):

    _api_endpoint_url = '/users/'

    def _get_objects_data(self, objects):
        users_data = []
        for user in objects:
            user_data = {f: getattr(user, f) for f in User.field_names}
            users_data.append(user_data)
        return users_data


class _GetUserUpdates(_PaginatedObjectsRetrieverWithUpdates):

    @property
    def _api_endpoint_url(self):
        if self.input_future_updates_url:
            url = self.input_future_updates_url
        else:
            url = '/users/'
        return url

    def _get_objects_data(self, objects):
        users_data = []
        for user in objects:
            user_data = {f: getattr(user, f) for f in User.field_names}
            users_data.append(user_data)
        return users_data


class _GetDeletedUsers(_PaginatedObjectsRetriever):

    _api_endpoint_url = '/users/deleted/'


class _GetDeletedUserUpdates(_PaginatedObjectsRetrieverWithUpdates):

    @property
    def _api_endpoint_url(self):
        if self.input_future_updates_url:
            url = self.input_future_updates_url
        else:
            url = '/users/deleted/'
        return url


class _GetGroups(_PaginatedObjectsRetriever):

    _api_endpoint_url = '/groups/'

    def _get_objects_data(self, objects):
        groups_data = []
        for group in objects:
            group_data = {f: getattr(group, f) for f in Group.field_names}
            groups_data.append(group_data)
        return groups_data


class _GetGroupMembers(_PaginatedObjectsRetriever):

    def __init__(self, objects, group_id):
        super(_GetGroupMembers, self).__init__(objects)

        self._group_id = group_id

    @property
    def _api_endpoint_url(self):
        return '/groups/{}/members/'.format(self._group_id)


class _ObjectWithUpdatesRetrievalTestCase(_ObjectsRetrievalTestCase):

    _UPDATES_SIMULATOR = abstractproperty()

    _API_URL_PATH = abstractproperty()

    def test_updates_retrieval(self):
        endpoint_url = 'http://example.com/api{}'.format(self._API_URL_PATH)

        future_updates_url = endpoint_url + '?use-this-for=future'
        self._check_future_updates_url(future_updates_url)

        future_updates_url_2 = endpoint_url + '?use-this-for=super-future'
        self._check_future_updates_url(future_updates_url_2, future_updates_url)

    @classmethod
    def _check_future_updates_url(cls, expected_url, input_url=None):
        simulator = cls._UPDATES_SIMULATOR([], expected_url, input_url)
        with MockConnection(simulator) as connection:
            _, url_retrieved = cls._DATA_RETRIEVER(connection, input_url)
        eq_(expected_url, url_retrieved)

    @classmethod
    def _retrieve_data(cls, connection):
        return cls._DATA_RETRIEVER(connection)[0]


class TestUsersRetrieval(_ObjectWithUpdatesRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_users)

    _SIMULATOR = staticmethod(_GetUsers)

    _UPDATES_SIMULATOR = staticmethod(_GetUserUpdates)

    _API_URL_PATH = '/users/'

    @staticmethod
    def _generate_deserialized_objects(count):
        users = []
        for counter in range(count):
            user = User(
                id=counter,
                full_name='User {}'.format(counter),
                email_address='user-{}@example.com'.format(counter),
                organization_name='Example Ltd',
                job_title='Employee {}'.format(counter),
                )
            users.append(user)
        return users


class TestDeletedUsersRetrieval(_ObjectWithUpdatesRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_deleted_users)

    _SIMULATOR = staticmethod(_GetDeletedUsers)

    _UPDATES_SIMULATOR = staticmethod(_GetDeletedUserUpdates)

    _API_URL_PATH = '/users/deleted/'

    @staticmethod
    def _generate_deserialized_objects(count):
        return list(range(count))


class TestGroupsRetrieval(_ObjectsRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_groups)

    _SIMULATOR = staticmethod(_GetGroups)

    @staticmethod
    def _generate_deserialized_objects(count):
        groups = [Group(id=i) for i in range(count)]
        return groups


class TestGroupMembersRetrieval(_ObjectsRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_group_members)

    _SIMULATOR = staticmethod(_GetGroupMembers)

    _GROUP_ID = 1

    def _retrieve_data(self, connection):
        return self._DATA_RETRIEVER(connection, self._GROUP_ID)

    def _make_simulator(self, objects):
        return self._SIMULATOR(objects, self._GROUP_ID)

    @staticmethod
    def _generate_deserialized_objects(count):
        return list(range(count))
