#!/usr/bin/python

# Copyright: (c) 2018, Terry Jones <terry.jones@example.org>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: organization

short_description: Module to create users in gitea api.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.0"

description: This module queries the gitea api and ensures a user is created.

options:
    name:
        description:
            - Name of the organization to be created.
            - Can include letters, numbers, and underscores only.
        required: true
        type: str
    owner:
        description: Username of the organization's owner.
        required: false
        type: str
    members:
        description: List of users to add as owners to the organization.
        required: false
        type: list
        elements: str

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
extends_documentation_fragment:
    - gsbtech.gitea_api.api
"""

EXAMPLES = r"""
# Create a public org with members.
- name: Test with members.
  gsbtech.gitea_api.organization:
    name: test-org
    owner: test
    members:
        - test2
        - test3
    visibility: public
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: present

# Create a limited org with no extra members.
- name: Test with no members.
  gsbtech.gitea_api.organization:
    name: test-org
    owner: test
    visibility: limited
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: present

# Remove an organization.
- name: Test removal.
  gsbtech.gitea_api.organization:
    name: test-org
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: absent
"""

RETURN = r"""
# These are examples of possible return values, and in general should use other names for return values.
organiztion_id:
    description: ID of the created organization.
    type: int
    returned: when state=present always returned; when state=absent only returned if changed
    sample: 1
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


def login_changed(module: AnsibleModule) -> bool:
    api_creds = (module.params["url_username"], module.params["url_password"])
    module.params["url_username"] = module.params["username"]
    module.params["url_password"] = module.params["password"]
    _, login_check = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/user",
        method="GET",
    )
    module.params["url_username"] = api_creds[0]
    module.params["url_password"] = api_creds[1]
    return login_check["status"] == 401


def api_get_user(module: AnsibleModule, result: dict) -> dict | None:
    users_req, users_req_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/admin/users?login_name={module.params['username']}",
        method="GET",
    )
    if users_req_info["status"] != 200:
        # during the execution of the module, if there is an exception or a
        # conditional state that effectively causes a failure, run
        # AnsibleModule.fail_json() to pass in the message and the result
        module.fail_json(
            msg=f"Failed to complete user list request: {users_req_info['body']}",
            **result,
        )
    user_list = module.from_json(users_req.read())
    return user_list[0] if len(user_list) == 1 else None


def remove_user(module: AnsibleModule, result: dict):
    targeted_user = api_get_user(module, result)

    if targeted_user is None:
        module.exit_json(**result)

    _, delete_user = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/admin/users/{module.params['username']}?purge=true",
        method="DELETE",
    )

    if delete_user["status"] != 204:
        module.fail_json(
            msg=f"Failed to complete user delete request: {delete_user['body']}",
            **result,
        )

    result["changed"] = True
    result["user_id"] = targeted_user["id"]
    module.exit_json(**result)


def create_or_update_user(module: AnsibleModule, result: dict):
    targeted_user = api_get_user(module, result)
    if targeted_user is not None:
        properties_to_check = ["email", "full_name", "visibility", "restricted"]
        property_changed = any(
            [targeted_user[prop] != module.params[prop] for prop in properties_to_check]
        )
        if property_changed or login_changed(module):
            user_update_body = {
                "email": module.params["email"],
                "full_name": module.params["full_name"],
                "visibility": module.params["visibility"],
                "restricted": module.params["restricted"],
                "password": module.params["password"],
                "login_name": module.params["username"],
            }
            user_update, user_update_info = fetch_url(
                module=module,
                url=f"https://{module.params['host']}/api/v1/admin/users/{module.params['username']}",
                headers={"Content-type": "application/json"},
                data=module.jsonify(user_update_body),
                method="PATCH",
            )
            if user_update_info["status"] != 200:
                module.fail_json(
                    msg=f"Failed to complete user update request: {user_update_info['body']}",
                    **result,
                )
            result["changed"] = True
        result["user_id"] = targeted_user["id"]
        module.exit_json(**result)

    create_user_body = {
        "login_name": module.params["username"],
        "username": module.params["username"],
        "password": module.params["password"],
        "email": module.params["email"],
        "full_name": module.params["full_name"],
        "restricted": module.params["restricted"],
        "visibility": module.params["visibility"],
        "must_change_password": False,
        "source_id": 0,
    }

    create_user_req, create_user_req_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/admin/users",
        headers={"Content-type": "application/json"},
        data=module.jsonify(create_user_body),
        method="POST",
    )

    if create_user_req_info["status"] != 201:
        module.fail_json(
            msg=f"Failed to complete user create request: {create_user_req_info['body']}",
            **result,
        )

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    result["user_id"] = module.from_json(create_user_req.read())["id"]
    result["changed"] = True
    module.exit_json(**result)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type="str", required=True),
        owner=dict(type="str", required=False),
        members=dict(type="list", elements="str", required=False),
        visibility=dict(
            type="str",
            required=False,
            default="private",
            choices=["public", "limited", "private"],
        ),
        host=dict(type="str", required=True),
        url_username=dict(type="str", required=True),
        url_password=dict(type="str", required=True, no_log=True),
        state=dict(
            type="str", required=False, default="present", choices=["present", "absent"]
        ),
    )

    module_args_required_if = [("state", "present", ("owner",))]

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        required_if=module_args_required_if,
        supports_check_mode=True,
    )

    # always set force_basic_auth to true
    module.params["force_basic_auth"] = True

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    if module.check_mode:
        module.exit_json(**result)

    match module.params["state"]:
        case "present":
            create_or_update_user(module, result)
        case "absent":
            remove_user(module, result)


def main():
    run_module()


if __name__ == "__main__":
    main()
