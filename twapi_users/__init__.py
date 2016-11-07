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

from itertools import chain

from pyrecord import Record
from voluptuous import Any
from voluptuous import Schema


BATCH_RETRIEVAL_SIZE_LIMIT = 200


User = Record.create_type(
    'User',
    'id',
    'full_name',
    'email_address',
    'organization_name',
    'job_title',
    'url',
    )


Group = Record.create_type('Group', 'id')


_USER_DATA_SCHEMA = Schema(
    {
        'id': int,
        'full_name': str,
        'email_address': str,
        'organization_name': str,
        'job_title': str,
        'url': str
        },
    required=True,
    extra=False,
    )


_USER_ID_SCHEMA = Schema(int)


_GROUP_DATA_SCHEMA = Schema({'id': int}, required=True, extra=False)


_PAGINATED_RESPONSE_SCHEMA = Schema(
    {
        'count': int,
        'next': Any(str, None),
        'results': [],
        },
    required=True,
    extra=True,
    )


def get_users(connection, updates_url=None):
    """
    Return information about each user that the client is allowed to know
    about.

    """
    users_data, future_updates_url = \
        _get_paginated_data_flattened_with_future_updates_url(
            connection,
            updates_url or '/users/',
            )
    return (_make_user(u) for u in users_data), future_updates_url


def get_user(connection, user_id):
    """Return information about user <user_id>."""
    return _retrieve_user_from_url(connection, '/users/{}/'.format(user_id))


def get_current_user(connection):
    """Return information about the current user."""
    user_url = _retrieve_current_url_canonical_url(connection)
    user = _retrieve_user_from_url(connection, user_url)
    return user


def _retrieve_user_from_url(connection, user_url):
    response = connection.send_get_request(user_url)
    user_data = response.json()
    user = _make_user(user_data)
    return user


def _retrieve_current_url_canonical_url(connection):
    response = connection.send_head_request('/self/')
    user_url = response.headers['Content-Location']
    return user_url


def _make_user(user_data):
    user_data = _USER_DATA_SCHEMA(user_data)
    user = User(**user_data)
    return user


def get_deleted_users(connection, updates_url=None):
    """Return the identifiers of the users that have been deleted."""
    users_data, future_updates_url = \
        _get_paginated_data_flattened_with_future_updates_url(
            connection,
            updates_url or '/users/deleted/',
            )
    return (_USER_ID_SCHEMA(u) for u in users_data), future_updates_url


def get_groups(connection):
    """
    Return information about each group that the client is allowed to know
    about.

    """
    groups_data = _get_paginated_data_flattened(connection, '/groups/')
    for group_data in groups_data:
        group_data = _GROUP_DATA_SCHEMA(group_data)
        group = Group(**group_data)
        yield group


def get_group_members(connection, group_id):
    """Return the user identifier for each member in group `group_id`."""
    url = '/groups/{}/members/'.format(group_id)
    users_data = _get_paginated_data_flattened(connection, url)
    for user_data in users_data:
        user_ids = _USER_ID_SCHEMA(user_data)
        yield user_ids


def _get_paginated_data_flattened(connection, url):
    paginated_data = _get_paginated_data(connection, url)
    paginated_data_flattened = _flatten_paginated_data(paginated_data)
    return paginated_data_flattened


def _get_paginated_data_flattened_with_future_updates_url(connection, url):
    paginated_data = _get_paginated_data(connection, url)

    first_page_response = next(paginated_data)
    future_updates_url = first_page_response.get('future_updates')

    paginated_data_restored = chain([first_page_response], paginated_data)
    paginated_data_flattened = _flatten_paginated_data(paginated_data_restored)

    return paginated_data_flattened, future_updates_url


def _flatten_paginated_data(pages):
    for page in pages:
        yield from page['results']


def _get_paginated_data(connection, url):
    while url:
        response = connection.send_get_request(url)
        response_data = response.json()
        response_data = _PAGINATED_RESPONSE_SCHEMA(response_data)

        yield response_data

        url = response_data['next']
