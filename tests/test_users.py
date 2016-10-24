##############################################################################
#
# Copyright (c) 2015-2016, 2degrees Limited.
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
from uuid import uuid4

from nose.tools import eq_
from twapi_connection.testing import MockConnection

from twapi_users import BATCH_RETRIEVAL_SIZE_LIMIT, get_users, User, \
    get_deleted_users, get_user, get_groups, Group, get_group_members, \
    get_current_user
from twapi_users.testing import GetUsers, GetUser, GetDeletedUsers, GetGroups, \
    GetGroupMembers, GetCurrentUser


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


class _ObjectWithUpdatesRetrievalTestCase(_ObjectsRetrievalTestCase):

    _API_URL_PATH = abstractproperty()

    def test_updates_retrieval(self):
        future_updates_url = self._generate_future_updates_url()
        self._check_future_updates_url(future_updates_url)

        future_updates_url_2 = self._generate_future_updates_url()
        self._check_future_updates_url(future_updates_url_2, future_updates_url)

    @classmethod
    def _check_future_updates_url(cls, expected_url, input_url=None):
        simulator = cls._SIMULATOR([], expected_url, input_url)
        with MockConnection(simulator) as connection:
            _, url_retrieved = cls._DATA_RETRIEVER(connection, input_url)
        eq_(expected_url, url_retrieved)

    @classmethod
    def _retrieve_data(cls, connection):
        return cls._DATA_RETRIEVER(connection)[0]

    def _make_simulator(self, objects):
        return self._SIMULATOR(objects, '')

    def _generate_future_updates_url(self):
        endpoint_url = 'http://example.com/api{}'.format(self._API_URL_PATH)
        random_str = str(uuid4())
        future_updates_url = endpoint_url + '?use-this-for=' + random_str
        return future_updates_url


class TestUsersRetrieval(_ObjectWithUpdatesRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_users)

    _SIMULATOR = staticmethod(GetUsers)

    _API_URL_PATH = '/users/'

    @staticmethod
    def _generate_deserialized_objects(count):
        return _generate_users(count)


class TestUserRetrieval:
    def test_user_retrieval(self):
        user = _generate_users(1)[0]
        simulator = GetUser(user)
        with MockConnection(simulator) as connection:
            retrieved_user = get_user(connection, user.id)
        eq_(user, retrieved_user)


class TestCurrentUserRetrieval:
    def test_user_retrieval(self):
        user = _generate_users(1)[0]
        simulator = GetCurrentUser(user)
        with MockConnection(simulator) as connection:
            retrieved_user = get_current_user(connection)
        eq_(user, retrieved_user)


class TestDeletedUsersRetrieval(_ObjectWithUpdatesRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_deleted_users)

    _SIMULATOR = staticmethod(GetDeletedUsers)

    _API_URL_PATH = '/users/deleted/'

    @staticmethod
    def _generate_deserialized_objects(count):
        return list(range(count))


class TestGroupsRetrieval(_ObjectsRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_groups)

    _SIMULATOR = staticmethod(GetGroups)

    @staticmethod
    def _generate_deserialized_objects(count):
        groups = [Group(id=i) for i in range(count)]
        return groups


class TestGroupMembersRetrieval(_ObjectsRetrievalTestCase):

    _DATA_RETRIEVER = staticmethod(get_group_members)

    _SIMULATOR = staticmethod(GetGroupMembers)

    _GROUP_ID = 1

    def _retrieve_data(self, connection):
        return self._DATA_RETRIEVER(connection, self._GROUP_ID)

    def _make_simulator(self, objects):
        return self._SIMULATOR(objects, self._GROUP_ID)

    @staticmethod
    def _generate_deserialized_objects(count):
        return list(range(count))


def _generate_users(count):
    users = []
    for counter in range(count):
        user = User(
            id=counter,
            full_name='User {}'.format(counter),
            email_address='user-{}@example.com'.format(counter),
            organization_name='Example Ltd',
            job_title='Employee {}'.format(counter),
            url='http://www.2degreesnetwork.com/api/users/{}'.format(counter)
            )
        users.append(user)
    return users
