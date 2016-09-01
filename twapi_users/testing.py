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

from abc import ABCMeta, abstractmethod, abstractproperty
from inspect import isgenerator
from itertools import islice

from twapi_connection.testing import SuccessfulAPICall, MockResponse

from twapi_users import BATCH_RETRIEVAL_SIZE_LIMIT
from twapi_users import Group
from twapi_users import User


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
        response = MockResponse(response_body_deserialization)
        api_call = SuccessfulAPICall(
            self._get_page_url(page_number),
            'GET',
            response=response,
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


class GetUsers(_PaginatedObjectsRetrieverWithUpdates):

    @property
    def _api_endpoint_url(self):
        if self.input_future_updates_url:
            url = self.input_future_updates_url
        else:
            url = '/users/'
        return url

    def _get_objects_data(self, objects):
        users_data = [_get_user_deserialization(user) for user in objects]
        return users_data


class _BaseUserRetriever(metaclass=ABCMeta):

    def __init__(self, user):
        super(_BaseUserRetriever, self).__init__()
        self._user = user

    @abstractmethod
    def __call__(self):
        pass

    def _make_user_retrieval_api_call(self):
        user_url = self._get_user_url()
        user_deserialization = _get_user_deserialization(self._user)
        response = MockResponse(user_deserialization)
        api_call = SuccessfulAPICall(user_url, 'GET', response=response)
        return api_call

    def _get_user_url(self):
        user_url = '/users/{}/'.format(self._user.id)
        return user_url


class GetUser(_BaseUserRetriever):

    def __call__(self):
        api_calls = [self._make_user_retrieval_api_call()]
        return api_calls


class GetCurrentUser(_BaseUserRetriever):

    def __call__(self):
        api_calls = [
            self._make_current_user_url_retrieval_api_call(),
            self._make_user_retrieval_api_call(),
        ]
        return api_calls

    def _make_current_user_url_retrieval_api_call(self):
        user_url = self._get_user_url()
        response = MockResponse(None, {'Content-Location': user_url})
        api_call = SuccessfulAPICall('/self/', 'HEAD', response=response)
        return api_call


class GetDeletedUsers(_PaginatedObjectsRetrieverWithUpdates):

    @property
    def _api_endpoint_url(self):
        if self.input_future_updates_url:
            url = self.input_future_updates_url
        else:
            url = '/users/deleted/'
        return url


class GetGroups(_PaginatedObjectsRetriever):

    _api_endpoint_url = '/groups/'

    def _get_objects_data(self, objects):
        groups_data = []
        for group in objects:
            group_data = {f: getattr(group, f) for f in Group.field_names}
            groups_data.append(group_data)
        return groups_data


class GetGroupMembers(_PaginatedObjectsRetriever):

    def __init__(self, objects, group_id):
        super(GetGroupMembers, self).__init__(objects)

        self._group_id = group_id

    @property
    def _api_endpoint_url(self):
        return '/groups/{}/members/'.format(self._group_id)


def _get_user_deserialization(user):
    user_deserialization = {f: getattr(user, f) for f in User.field_names}
    return user_deserialization
