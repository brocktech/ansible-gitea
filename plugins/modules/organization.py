#!/usr/bin/python

# Copyright: (c) 2024, Curtis Jones <cjones2@brocku.ca>
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
    - gsbtech.gitea_api.api.visibility
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


def api_get_org(module: AnsibleModule, result: dict) -> dict | None:
    orgs_req, orgs_req_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs",
        method="GET",
    )

    if orgs_req_info["status"] != 200:
        # during the execution of the module, if there is an exception or a
        # conditional state that effectively causes a failure, run
        # AnsibleModule.fail_json() to pass in the message and the result
        module.fail_json(
            msg=f"Failed to complete organization list request: {orgs_req_info['body']}",
            **result,
        )

    return next(
        (
            org
            for org in module.from_json(orgs_req.read())
            if org["name"] == module.params["name"]
        ),
        None,
    )


def remove_org(module: AnsibleModule):
    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    targeted_org = api_get_org(module, result)

    if targeted_org is None:
        module.exit_json(**result)

    _, delete_org = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{module.params['name']}",
        method="DELETE",
    )

    if delete_org["status"] != 204:
        module.fail_json(
            msg=f"Failed to complete organization delete request: {delete_org['body']}",
            **result,
        )

    result["changed"] = True
    result["organization_id"] = targeted_org["id"]
    module.exit_json(**result)


def create_org(module: AnsibleModule, result: dict) -> dict:

    create_org_req, create_org_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/admin/users/{module.params['owner']}/orgs",
        headers={"Content-type": "application/json"},
        method="POST",
        data=module.jsonify(
            {
                "username": module.params["name"],
                "visibility": module.params["visibility"],
            }
        ),
    )

    if create_org_info["status"] != 201:
        module.fail_json(
            msg=f"Failed to complete organization create request: {create_org_info['body']}",
            **result,
        )

    result["changed"] = True

    return module.from_json(create_org_req.read())


def update_org_members(module: AnsibleModule, result: dict, org: dict):
    team_list_req, team_list_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/orgs/{org['name']}/teams",
        method="GET",
    )

    if team_list_info["status"] != 200:
        module.fail_json(
            msg=f"Failed to complete organization team list request: {team_list_info['body']}",
            **result,
        )

    owner_team = next(
        (
            team
            for team in module.from_json(team_list_req.read())
            if team["name"] == "Owners"
        ),
        None,
    )

    if owner_team is None:
        module.fail_json(
            msg=f"Owner team was not present for [{org['name']}].",
            **result,
        )

    owners_req, owners_info = fetch_url(
        module=module,
        url=f"https://{module.params['host']}/api/v1/teams/{owner_team['id']}/members",
        method="GET",
    )

    if owners_info["status"] != 200:
        module.fail_json(
            msg=f"Failed to complete organization owners members list request: {owners_info['body']}",
            **result,
        )

    owners = module.from_json(owners_req.read())
    expected_members = [module.params["owner"]] + module.params["members"]

    for member in expected_members:
        if (
            next((owner for owner in owners if owner["login_name"] == member), None)
            is None
        ):
            _, owner_info = fetch_url(
                module=module,
                url=f"https://{module.params['host']}/api/v1/teams/{owner_team['id']}/members/{member}",
                method="PUT",
            )

            if owner_info["status"] != 204:
                module.fail_json(
                    msg=f"Failed to add user({member}) to org({org['name']}) owners: {owner_info['body']}",
                    **result,
                )
            result["changed"] = True


def create_and_update_org(module: AnsibleModule):
    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    targeted_org = api_get_org(module, result)
    targeted_org = (
        targeted_org if targeted_org is not None else create_org(module, result)
    )

    if targeted_org["visibility"] != module.params["visibility"]:
        _, vis_update_info = fetch_url(
            module=module,
            url=f"https://{module.params['host']}/api/v1/orgs/{targeted_org['name']}",
            headers={"Content-type": "application/json"},
            method="PATCH",
            data=module.jsonify({"visibility": module.params["visibility"]}),
        )

        if vis_update_info["status"] != 200:
            module.fail_json(
                msg=f"Failed to update visibilty to {module.params['visibility']} for org({targeted_org['name']}): {vis_update_info['body']}",
                **result,
            )

    update_org_members(module, result, targeted_org)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    result["organization_id"] = targeted_org["id"]
    module.exit_json(**result)


def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        name=dict(type="str", required=True),
        owner=dict(type="str", required=False),
        members=dict(type="list", elements="str", required=False, default=[]),
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
            create_and_update_org(module)
        case "absent":
            remove_org(module)


def main():
    run_module()


if __name__ == "__main__":
    main()
