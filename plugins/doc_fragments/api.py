#!/usr/bin/python

# Copyright: (c) 2024, Curtis Jones <cjones2@brocku.ca>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):
    DOCUMENTATION = r"""
---
attributes:
    check_mode:
        support: full
        description: Can run in C(check_mode) and return changed status prediction without modifying target.
    diff_mode:
        support: none
        description: Will return details on what has changed (or possibly needs changing in C(check_mode)), when in diff mode.

options:
    host:
        description: Hostname of the gitea server.
        required: true
        type: str
    url_username:
        description: Username for HTTP API Basic Auth.
        required: true
        type: str
    url_password:
        description: Password for HTTP API Basic Auth.
        required: true
        type: str
    state:
        description: State of the object in Gitea.
        required: false
        type: str
        default: 'present'
        choices:
            - 'present'
            - 'absent'

author:
    - Curtis Jones (@ikubetoomuzik)
"""
    VISIBILITY = r"""
---
options:
    visibility:
        description: Visibility in gitea.
        required: false
        type: str
        default: 'private'
        choices:
            - 'public'
            - 'limited'
            - 'private'
"""
