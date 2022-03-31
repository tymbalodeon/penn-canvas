from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from canvasapi import Canvas
from canvasapi.account import Account
from canvasapi.paginated_list import PaginatedList
from canvasapi.requester import Requester
from cx_Oracle import connect, init_oracle_client
from loguru import logger
from requests.models import Response
from typer import Exit, echo, style

from .config import get_config_option, get_penn_canvas_config
from .constants import OPEN_CANVAS_MAIN_ACCOUNT_ID, PENN_CANVAS_MAIN_ACCOUNT_ID
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
    OPEN_BETA = "open_beta"


def get_data_warehouse_cursor():
    user, password, dsn = get_penn_canvas_config("data_warehouse")
    return connect(user, password, dsn).cursor()


def print_instance(instance: Instance):
    instance_name = instance.name.replace("_", " ")
    echo(f"INSTANCE: {style(instance_name, bold=True)} Canvas")


def validate_instance_name(instance_name: str | Instance, verbose=False):
    if isinstance(instance_name, Instance):
        instance = instance_name
    else:
        instance_names = [instance.value for instance in Instance]
        if instance_name not in instance_names:
            echo(f'ERROR: Invalid instance name "{instance_name}"')
            echo("\nAvailable instances are:")
            for name in instance_names:
                echo(f'\t"{name}"')
            raise Exit()
        instance = Instance(instance_name)
    if verbose:
        print_instance(instance)
    return instance


def format_instance_name(instance: Instance) -> str:
    return f"_{instance.name}"


def get_canvas_url_and_key(instance=Instance.PRODUCTION) -> tuple[str, str]:
    url, key = {
        Instance.PRODUCTION: ("canvas_prod_url", "canvas_prod_key"),
        Instance.TEST: ("canvas_test_url", "canvas_test_key"),
        Instance.BETA: ("canvas_beta_url", "canvas_beta_key"),
        Instance.OPEN: ("open_canvas_prod_url", "open_canvas_prod_key"),
        Instance.OPEN_TEST: ("open_canvas_test_url", "open_canvas_test_key"),
        Instance.OPEN_BETA: ("open_canvas_beta_url", "open_canvas_beta_key"),
    }.get(instance, ("canvas_prod_url", "canvas_prod_key"))
    return (
        get_config_option("canvas_urls", url),
        get_config_option("canvas_keys", key),
    )


def get_canvas(instance=Instance.PRODUCTION, verbose=True, override_key=None) -> Canvas:
    instance = validate_instance_name(instance)
    url, key = get_canvas_url_and_key(instance)
    if override_key:
        key = override_key
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
    account: Optional[int] | Optional[Account] = None,
    use_sis_id=False,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> Account:
    if not account:
        account = get_main_account_id(instance)
    elif isinstance(account, Account):
        return account
    instance = validate_instance_name(instance)
    try:
        account_object = get_canvas(instance, verbose=verbose).get_account(
            account, use_sis_id=use_sis_id
        )
        if verbose:
            pprint(account)
        return account_object
    except Exception as error:
        logger.error(error)
        raise Exit()


def get_course(
    course_id: str | int,
    use_sis_id=False,
    include=None,
    instance=Instance.PRODUCTION,
    verbose=False,
    pretty_print=False,
):
    try:
        course = get_canvas(instance, verbose).get_course(
            course_id, use_sis_id, include=include
        )
    except Exception as error:
        echo(f"ERROR: Failed to find course ({error})")
        logger.error(error)
        raise Exit(1)
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


def get_main_account_id(instance: Instance) -> int:
    return {
        Instance.PRODUCTION: PENN_CANVAS_MAIN_ACCOUNT_ID,
        Instance.TEST: PENN_CANVAS_MAIN_ACCOUNT_ID,
        Instance.BETA: PENN_CANVAS_MAIN_ACCOUNT_ID,
        Instance.OPEN: OPEN_CANVAS_MAIN_ACCOUNT_ID,
        Instance.OPEN_TEST: OPEN_CANVAS_MAIN_ACCOUNT_ID,
        Instance.OPEN_BETA: OPEN_CANVAS_MAIN_ACCOUNT_ID,
    }.get(instance, PENN_CANVAS_MAIN_ACCOUNT_ID)


def get_sub_account_ids(
    account_id: Optional[int] = None,
    instance=Instance.PRODUCTION,
    verbose=False,
) -> list[str]:
    if not account_id:
        account_id = get_main_account_id(instance)
    account = get_canvas(instance, verbose).get_account(account_id)
    account_ids = [account_id] + [
        account.id for account in account.get_subaccounts(recursive=True)
    ]
    return [str(account_id) for account_id in account_ids]


def get_enrollment_term_id(
    term_name: str,
    account: int | Account = PENN_CANVAS_MAIN_ACCOUNT_ID,
    instance: Instance = Instance.PRODUCTION,
) -> int:
    account = get_account(account, instance=instance)
    term_id = next(
        (term.id for term in account.get_enrollment_terms() if term_name in term.name),
        None,
    )
    if not term_id:
        enrollment_terms = [term.name for term in account.get_enrollment_terms()]
        echo(f"- ERROR: Enrollment term not found: {term_name}")
        echo("- Available enrollment terms are:")
        for enrollment_term in enrollment_terms:
            echo(f"\t{enrollment_term}")
        raise Exit()
    else:
        return term_id


def request_external_url(
    url: str, instance=Instance.PRODUCTION, method="GET"
) -> Response:
    canvas_url, key = get_canvas_url_and_key(instance)
    return Requester(canvas_url, key).request(method, _url=url)


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


def collect(paginator: PaginatedList | Iterable) -> list:
    return [item for item in paginator]
