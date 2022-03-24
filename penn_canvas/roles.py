from loguru import logger
from pandas import DataFrame

from penn_canvas.api import (
    collect,
    get_account,
    get_sub_account_ids,
    validate_instance_name,
)
from penn_canvas.helpers import (
    BASE_PATH,
    TODAY_AS_Y_M_D,
    create_directory,
    switch_logger_file,
)
from penn_canvas.style import print_item

COMMAND_PATH = create_directory(BASE_PATH / "Roles")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")


def get_role_data(account_id, permission, verbose):
    account = get_account(account_id)
    roles = collect(account.get_roles())
    roles = [
        [
            account.name,
            account.id,
            role.role,
            role.label,
            role.permissions[permission]["enabled"],
        ]
        for role in roles
    ]
    if verbose:
        total = len(roles)
        for index, role in enumerate(roles):
            print_item(index, total, role)
    return roles


def roles_main(permission: str, instance_name: str, verbose: bool):
    instance = validate_instance_name(instance_name)
    switch_logger_file(LOGS, "roles", instance.name)
    try:
        account_ids = [int(account) for account in get_sub_account_ids()]
        roles = [
            get_role_data(account_id, permission, verbose) for account_id in account_ids
        ]
        roles = [item for sublist in roles for item in sublist]
        data_frame = DataFrame(
            roles,
            columns=[
                "Account Name",
                "Account ID",
                "Role",
                "Role Label",
                f"{permission.replace('_', ' ').title()} enabled?",
            ],
        )
        data_frame.to_csv(
            RESULTS / f"{permission}_permissions_{TODAY_AS_Y_M_D}.csv", index=False
        )
    except Exception as error:
        logger.error(error)
