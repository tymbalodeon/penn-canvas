from pathlib import Path

from pandas.core.frame import DataFrame

from penn_canvas.api import collect, get_account, get_sub_account_ids


def get_role_data(account_id):
    account = get_account(account_id)
    roles = collect(account.get_roles())
    roles = [
        [
            account.name,
            account.id,
            role.role,
            role.label,
            role.permissions["view_statistics"]["enabled"],
        ]
        for role in roles
    ]
    for role in roles:
        print(role)
    return roles


def get_roles():
    account_ids = [int(account) for account in get_sub_account_ids()]
    roles = [get_role_data(account_id) for account_id in account_ids]
    roles = [item for sublist in roles for item in sublist]
    data_frame = DataFrame(
        roles,
        columns=[
            "Account Name",
            "Account ID",
            "Role",
            "Role Label",
            "View Statistics Enabled?",
        ],
    )
    data_frame.to_csv(
        Path.home() / "Desktop/view_statistics_permissions.csv", index=False
    )
    return roles
