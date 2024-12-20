#!/usr/bin/python

# Copyright: (c) 2024, Curtis Jones <cjones2@brocku.ca>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: secret

short_description: Module to create action secrets in the gitea api.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.0"

description: This module queries the gitea api and ensures a secret is created/removed.

options:
    name:
        description:
            - Name of the secret to be created.
            - Can include letters, numbers, and underscores only.
        required: true
        type: str
    value:
        description:
            - Value of the secret.
            - Only required when state=present
        required: false
        type: str
    force_update:
        description:
            - Secret values cannot be read once set, use this to update secrets.
            - Will always run as changed when set.
        required: false
        type: bool
        default: false
    organization:
        description: Name of organizaion to add/remove from.
        required: true
        type: list
        elements: str

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
extends_documentation_fragment:
    - gsbtech.gitea_api.api
"""

EXAMPLES = r"""
# Create a secret.
- name: Create secret in an org.
  gsbtech.gitea_api.secret:
    name: test-secret
    value: test
    organization: test-org
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: present

# Update a secret.
- name: Update secret in an org.
  gsbtech.gitea_api.secret:
    name: test-secret
    value: test
    organization: test-org
    force_update: true
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: present

# Remove a secret.
- name: Create secret in an org.
  gsbtech.gitea_api.secret:
    name: test-secret
    organization: test-org
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: absent
"""

RETURN = r"""
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url


def api_get_secret(module: AnsibleModule, result: dict) -> dict | None:
    secrets_req, secrets_req_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/secrets",
        method="GET",
    )

    if secrets_req_info["status"] != 200:
        # during the execution of the module, if there is an exception or a
        # conditional state that effectively causes a failure, run
        # AnsibleModule.fail_json() to pass in the message and the result
        module.fail_json(
            msg=f"Failed to complete secret list request for org({module.params['organization']}): {secrets_req_info['body']}",
            **result,
        )

    return next(
        (
            secret
            for secret in module.from_json(secrets_req.read())
            if secret["name"] == module.params["name"].upper()
        ),
        None,
    )


def remove_secret(module: AnsibleModule):
    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    targeted_secret = api_get_secret(module, result)

    if targeted_secret is None:
        module.exit_json(**result)

    _, delete_secret = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/secrets/{module.params['name']}",
        method="DELETE",
    )

    if delete_secret["status"] != 204:
        module.fail_json(
            msg=f"Failed to delete secret({module.params['name']}) from org({module.params['organization']}) request: {delete_secret['body']}",
            **result,
        )

    result["changed"] = True
    module.exit_json(**result)


def create_secret(module: AnsibleModule, result: dict) -> dict:
    _, create_secret_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/secrets/{module.params['name']}",
        headers={"Content-type": "application/json"},
        method="PUT",
        data=module.jsonify(
            {
                "data": module.params["value"],
            }
        ),
    )

    if create_secret_info["status"] != 201:
        module.fail_json(
            msg=f"Failed to create secret({module.params['name']}) in org({module.params['organization']}) req: {create_secret_info['body']}",
            **result,
        )

    result["changed"] = True

    return api_get_secret(module, result)


def update_secret_value(module: AnsibleModule, result: dict):
    _, secret_upd_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/secrets/{module.params['name']}",
        headers={"Content-type": "application/json"},
        method="PUT",
        data=module.jsonify({"data": module.params["value"]}),
    )

    if secret_upd_info["status"] != 204:
        module.fail_json(
            msg=f"Failed to update secret({module.params['name']}) in org({module.params['organization']}) request: {secret_upd_info['body']}",
            **result,
        )

    result["changed"] = True


def create_and_update_secret(module: AnsibleModule):
    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    if api_get_secret(module, result) is None:
        create_secret(module, result)
    elif module.params["force_update"]:
        update_secret_value(module, result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type="str", required=True),
        value=dict(type="str", required=False, no_log=True),
        organization=dict(
            type="str",
            required=True,
        ),
        force_update=dict(type="bool", required=False, default=False),
        host=dict(type="str", required=True),
        url_username=dict(type="str", required=True),
        url_password=dict(type="str", required=True, no_log=True),
        state=dict(
            type="str", required=False, default="present", choices=["present", "absent"]
        ),
    )

    module_args_required_if = [("state", "present", ("value",))]

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
        no_log=False,
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
            create_and_update_secret(module)
        case "absent":
            remove_secret(module)


def main():
    run_module()


if __name__ == "__main__":
    main()
