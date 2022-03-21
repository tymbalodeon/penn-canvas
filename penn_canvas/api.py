from enum import Enum
from pathlib import Path
from typing import Callable

from canvasapi import Canvas
from canvasapi.account import Account
from canvasapi.paginated_list import PaginatedList
from cx_Oracle import connect, init_oracle_client
from loguru import logger
from typer import Exit, echo, style

from .config import get_penn_canvas_config
from .constants import MAIN_ACCOUNT_ID
from .style import pprint

lib_dir = Path.home() / "Downloads/instantclient_19_8"
config_dir = lib_dir / "network/admin"
init_oracle_client(
    lib_dir=str(lib_dir),
    config_dir=str(config_dir),
)


class Instance(Enum):
    PRODUCTION = "prod"
    TEST = "test"
    BETA = "beta"
    OPEN = "open"
    OPEN_TEST = "open_test"


def get_data_warehouse_cursor():
    user, password, dsn = get_penn_canvas_config("data_warehouse")
    return connect(user, password, dsn).cursor()


def validate_instance_name(instance_name, verbose=False):
    if isinstance(instance_name, Instance):
        instance = instance_name
    else:
        instances = [instance.value for instance in Instance]
        if instance_name not in instances:
            echo(f'ERROR: Invalid instance name "{instance_name}"')
            echo("\nAvailable instances are:")
            for instance in instances:
                echo(f'\t"{instance}"')
            raise Exit()
        instance = Instance(instance_name)
    if verbose:
        print_instance(instance)
    return instance


def print_instance(instance: Instance):
    instance_name = instance.name.replace("_", " ")
    echo(f"INSTANCE: {style(instance_name, bold=True)} Canvas")


def format_instance_name(instance: Instance) -> str:
    return f"_{instance.name}"


def get_canvas(instance=Instance.PRODUCTION, verbose=True, override_key=None) -> Canvas:
    instance = validate_instance_name(instance)
    canvas_urls = get_penn_canvas_config("canvas_urls")
    canvas_keys = get_penn_canvas_config("canvas_keys")
    (
        canvas_prod_key,
        canvas_test_key,
        canvas_beta_key,
        open_canvas_key,
        open_canvas_test_key,
    ) = canvas_keys
    (
        canvas_prod_url,
        canvas_test_url,
        canvas_beta_url,
        open_canvas_url,
        open_canvas_test_url,
    ) = canvas_urls
    url = canvas_prod_url
    key = override_key or canvas_prod_key
    if instance == Instance.TEST:
        url = canvas_test_url
        key = override_key or canvas_test_key
    elif instance == Instance.BETA:
        url = canvas_beta_url
        key = override_key or canvas_beta_key
    elif instance == Instance.OPEN:
        url = open_canvas_url
        key = override_key or open_canvas_key
    elif instance == Instance.OPEN_TEST:
        url = open_canvas_test_url
        key = override_key or open_canvas_test_key
    canvas = Canvas(url, key)
    try:
        canvas.get_accounts()
        if verbose:
            print_instance(instance)
        return canvas
    except Exception as error:
        logger.error(error)
        logger.error(f"URL: {url}")
        logger.error(f"KEY: {key}")
        raise SystemExit(f'Failed to connect to Canvas: "{error}"')


def get_account(
    account: int | Account = MAIN_ACCOUNT_ID,
    use_sis_id=False,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Account:
    if isinstance(account, Account):
        return account
    instance = validate_instance_name(instance)
    try:
        account_object = get_canvas(instance, verbose=verbose).get_account(
            account, use_sis_id=use_sis_id
        )
    except Exception as error:
        logger.error(error)
    if verbose:
        pprint(account)
    return account_object


def get_course(
    course_id: str | int,
    use_sis_id=False,
    include=None,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    course = get_canvas(instance, verbose).get_course(
        course_id, use_sis_id, include=include
    )
    if pretty_print:
        pprint(course)
    return course


def get_section(
    section_id: str | int,
    use_sis_id=False,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    section = get_canvas(instance, verbose).get_section(section_id, use_sis_id)
    if pretty_print:
        pprint(section)
    return section


def get_user(
    user_id: str | int,
    id_type=None,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    user = get_canvas(instance, verbose).get_user(user_id, id_type=id_type)
    if pretty_print:
        pprint(user)
    return user


def get_sub_accounts(account_id: int, instance: Instance, verbose=False) -> list[str]:
    account = get_canvas(instance, verbose).get_account(account_id)
    return [str(account_id)] + [
        str(account.id) for account in account.get_subaccounts(recursive=True)
    ]


def get_external_tool_names(verbose=False):
    account = get_account()
    sub_accounts = collect(account.get_subaccounts(recursive=True))
    external_tool_names = list()
    for sub_account in sub_accounts:
        external_tool_names = external_tool_names + [
            tool.name.lower() for tool in collect(sub_account.get_external_tools())
        ]
    external_tool_names = sorted(set(external_tool_names))
    if verbose:
        print(*external_tool_names, sep="\n")
    return external_tool_names


def collect(
    paginator: PaginatedList | list,
    function: Callable | None = None,
    conditional_function: Callable | None = None,
) -> list:
    if function:
        return [function(item) for item in paginator]
    elif conditional_function:
        return [item for item in paginator if conditional_function(item)]
    else:
        return [item for item in paginator]
