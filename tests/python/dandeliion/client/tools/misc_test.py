"""
@file tests/python/dandeliion/client/tools/misc_test.py

Testing the routines for dandeliion.client.tools.misc
"""

#
# Copyright (C) 2024-2025 Dandeliion Team
#
# This library is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 3.0 of the License, or (at your option)
# any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#

# built-in modules
import copy

#custom modules
from dandeliion.client.tools import misc


def test_update_dict_default():
    """
    Test case for update_dict with default args (inline + not forcing None updates)
    """
    target = {'a': 1, 'b': {'aa': 2, 'ab': 3}, 'c': {'ca': {'caa': 'some'}, 'cb': 4}, 'd': None}
    updates = {'a': 1, 'b': None, 'c': {'ca': {'caa': 5}}, 'd': {'da': None}}

    misc.update_dict(target, updates)

    assert target == {'a': 1, 'b': {'aa': 2, 'ab': 3}, 'c': {'ca': {'caa': 5}, 'cb': 4}, 'd': {'da': None}}


def test_update_dict_force_none():
    """
    Test case for update_dict with inline + forcing None updates
    """
    target = {'a': 1, 'b': {'aa': 2, 'ab': 3}, 'c': {'ca': {'caa': 'some'}, 'cb': 4}, 'd': None}
    updates = {'a': 1, 'b': None, 'c': {'ca': {'caa': 5}}, 'd': {'da': None}}

    misc.update_dict(target, updates, inline=True, force_none=True)

    assert target == {'a': 1, 'b': None, 'c': {'ca': {'caa': 5}, 'cb': 4}, 'd': {'da': None}}


def test_update_dict_not_inline():
    """
    Test case for update_dict with inline + forcing None updates
    """
    target = {'a': 1, 'b': {'aa': 2, 'ab': 3}, 'c': {'ca': {'caa': 'some'}, 'cb': 4}, 'd': None}
    target_backup = copy.deepcopy(target)
    updates = {'a': 1, 'b': None, 'c': {'ca': {'caa': 5}}, 'd': {'da': None}}

    result = misc.update_dict(target, updates, inline=False)

    assert target == target_backup
    assert result == {'a': 1, 'b': {'aa': 2, 'ab': 3}, 'c': {'ca': {'caa': 5}, 'cb': 4}, 'd': {'da': None}}
