#!/usr/bin/python

# Copyright: (c) 2024, Curtis Jones <cjones2@brocku.ca>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: variable

short_description: Module to create action variables in the gitea api.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.0"

description: This module queries the gitea api and ensures a variable is created/removed.

options:
    name:
        description:
            - Name of the variable to be created.
            - Can include letters, numbers, and underscores only.
        required: true
        type: str
    value:
        description:
            - Value of the variable.
            - Only required when state=present
        required: false
        type: str
    organization:
        description: Name of organizaion to add/remove from.
        required: true
        type: list
        elements: str

# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
extends_documentation_fragment:
    - brocktech.gitea.api
"""

EXAMPLES = r"""
# Create a variable.
- name: Create var in an org.
  brocktech.gitea.variable:
    name: test-var
    value: test
    organization: test-org
    host: gitea.example.com
    url_username: <api_username>
    url_password: <api_password>
    state: present

# Remove a variable.
- name: Create var in an org.
  brocktech.gitea.variable:
    name: test-var
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


def api_get_var(module: AnsibleModule, result: dict) -> dict | None:
    vars_req, vars_req_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/variables/{module.params['name']}",
        method="GET",
    )

    if vars_req_info["status"] == 400:
        # during the execution of the module, if there is an exception or a
        # conditional state that effectively causes a failure, run
        # AnsibleModule.fail_json() to pass in the message and the result
        module.fail_json(
            msg=f"Failed to complete organization list request: {vars_req_info['body']}",
            **result,
        )

    return module.from_json(vars_req.read()) if vars_req_info["status"] == 200 else None


def remove_var(module: AnsibleModule):
    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    targeted_var = api_get_var(module, result)

    if targeted_var is None:
        module.exit_json(**result)

    _, delete_var = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/variables/{module.params['name']}",
        method="DELETE",
    )

    if delete_var["status"] != 204:
        module.fail_json(
            msg=f"Failed to complete var({module.params['name']}) delete from org({module.params['organization']}) request: {delete_var['body']}",
            **result,
        )

    result["changed"] = True
    module.exit_json(**result)


def create_var(module: AnsibleModule, result: dict) -> dict:

    _, create_var_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/variables/{module.params['name']}",
        headers={"Content-type": "application/json"},
        method="POST",
        data=module.jsonify(
            {
                "value": module.params["value"],
            }
        ),
    )

    if create_var_info["status"] != 204 and create_var_info["status"] != 201:
        module.fail_json(
            msg=f"Failed to complete var({module.params['name']}) create from org({module.params['organization']}) req: {create_var_info['body']}",
            **result,
        )

    result["changed"] = True

    return api_get_var(module, result)


def update_var_value(module: AnsibleModule, result: dict, variable: dict):
    if variable["data"] == module.params["value"]:
        return

    var_upd_req, var_upd_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['organization']}/actions/variables/{module.params['name']}",
        headers={"Content-type": "application/json"},
        method="PUT",
        data=module.jsonify({"value": module.params["value"]}),
    )

    if var_upd_info["status"] != 204 and var_upd_info["status"] != 201:
        module.fail_json(
            msg=f"Failed to update var({module.params['name']}) in org({module.params['organization']}) request: {var_upd_info['body']}",
            **result,
        )

    result["changed"] = True


def create_and_update_var(module: AnsibleModule):
    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    targeted_var = api_get_var(module, result)
    targeted_var = (
        targeted_var if targeted_var is not None else create_var(module, result)
    )

    update_var_value(module, result, targeted_var)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type="str", required=True),
        value=dict(type="str", required=False),
        organization=dict(
            type="str",
            required=True,
        ),
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
            create_and_update_var(module)
        case "absent":
            remove_var(module)


def main():
    run_module()


if __name__ == "__main__":
    main()
