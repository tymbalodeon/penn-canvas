from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path
from typing import NamedTuple

from canvasapi.communication_channel import CommunicationChannel
from canvasapi.user import User
from pandas import concat, read_csv
from pandas.core.frame import DataFrame
from typer import Exit, echo, progressbar

from penn_canvas.report import get_report
from penn_canvas.style import print_item

from .helpers import (
    BASE_PATH,
    CURRENT_YEAR_AND_TERM,
    TODAY_AS_Y_M_D,
    YEAR,
    Instance,
    add_headers_to_empty_files,
    color,
    confirm_global_protect_enabled,
    create_directory,
    drop_duplicate_errors,
    dynamic_to_csv,
    format_instance_name,
    get_account,
    get_data_warehouse_cursor,
    get_processed,
    get_start_index,
    get_user,
    handle_clear_processed,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    validate_instance_name,
)

COMMAND_PATH = create_directory(BASE_PATH / "Email")
LOGS = COMMAND_PATH / "logs"
PROCESSED = COMMAND_PATH / ".processed"
HEADERS = [
    "canvas user id",
    "login id",
    "full name",
    "email status",
    "supported",
    "subaccount",
]
LOG_HEADERS = HEADERS[:3]
LOG_HEADERS.extend(["email address"])
ACCOUNTS = [
    99243,
    99237,
    128877,
    99241,
    99244,
    99238,
    99239,
    131428,
    99240,
    132153,
    82192,
]
PRINT_COLOR_MAPS = {
    "already active": "cyan",
    "activated": "green",
    "failed to activate": "red",
    "unconfirmed": "yellow",
    "user not found": "red",
    "not found": "red",
    "error": "red",
}


def process_report(
    report_path: Path,
    processed_users: list[str],
    processed_errors: list[str],
    new: bool,
) -> tuple[DataFrame, int]:
    report = read_csv(report_path)
    report.drop_duplicates(subset=["canvas_user_id"], inplace=True)
    report.sort_values(
        "canvas_user_id", ascending=False, inplace=True, ignore_index=True
    )
    report = report.astype("string", copy=False, errors="ignore")
    report = report[~report["canvas_user_id"].isin(processed_users)]
    already_processed_count = len(processed_users)
    if new:
        report = report[~report["canvas_user_id"].isin(processed_errors)]
        already_processed_count = already_processed_count + len(processed_errors)
    if already_processed_count:
        message = color(
            f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
            f" {'USER' if already_processed_count == 1 else 'USERS'}...",
            "yellow",
        )
        echo(f") {message}")
    return report, len(report.index)


def get_user_emails(user: User) -> list[CommunicationChannel]:
    return [
        channel
        for channel in user.get_communication_channels()
        if channel.type == "email"
    ]


def get_email_status(email: CommunicationChannel) -> bool:
    return email.workflow_state == "active"


def is_already_active(
    user: NamedTuple, instance: str | Instance
) -> tuple[str, User | None, list[CommunicationChannel] | None]:
    user_id = user[1]
    canvas_user = None
    emails = None
    try:
        canvas_user = get_user(user_id, instance)
    except Exception:
        return "user not found", canvas_user, emails
    try:
        emails = get_user_emails(canvas_user)
    except Exception:
        return "error", canvas_user, emails
    emails_iterator = iter(emails)
    email = next(emails_iterator, None)
    if email:
        is_active = get_email_status(email)
        while not is_active:
            next_email = next(emails_iterator, None)
            if not next_email:
                return "unconfirmed", canvas_user, emails
            is_active = get_email_status(next_email)
        return "already active", canvas_user, emails
    else:
        return "not found", canvas_user, emails


def check_schools(
    canvas_user: User, sub_accounts: list[int]
) -> tuple[bool, int | None]:
    account_ids = [course.account_id for course in canvas_user.get_courses()]
    fixable_id = next(
        (account for account in account_ids if account in sub_accounts), None
    )
    return (bool(fixable_id), account_ids[0]) if len(account_ids) else (False, None)


def activate_user_email(
    canvas_user_id: str,
    login_id: str,
    full_name: str,
    canvas_user: User,
    emails: list[CommunicationChannel],
    log_path: Path,
) -> str:
    for email in emails:
        new_add = isinstance(email, str)
        user_info = [
            canvas_user_id,
            login_id,
            full_name,
            email if new_add else email.address,
        ]
        with open(log_path, "a", newline="") as result:
            writer(result).writerow(user_info)
        if not new_add:
            email.delete()
        canvas_user.create_communication_channel(
            communication_channel={
                "address": email if new_add else email.address,
                "type": "email",
            },
            skip_confirmation=True,
        )
    email_iterator = iter(get_user_emails(canvas_user))
    inactive = True
    while inactive:
        next_email = next(email_iterator, None)
        if not next_email:
            return "failed to activate"
        inactive = get_email_status(next_email)
    log = read_csv(log_path)
    log.drop(index=log.index[-1:], inplace=True)
    log.to_csv(log_path, index=False)
    return "activated"


def remove_empty_log(log_path):
    if log_path.is_file() and read_csv(log_path).empty:
        echo(") Removing empty log file...")
        remove(log_path)


def process_result(result_path, new):
    result = read_csv(result_path)
    supported = result[result["supported"] == "Y"]
    unsupported = result[result["supported"] == "N"]
    activated = supported[supported["email status"] == "activated"].copy()
    already_active = result[result["email status"] == "already active"]
    failed_to_activate = supported[supported["email status"] == "failed to activate"]
    supported_not_found = supported[supported["email status"] == "not found"]
    error_supported = supported[supported["email status"] == "error"]
    users_not_found = result[result["email status"] == "user not found"].copy()
    error_unsupported = unsupported[unsupported["email status"] == "error"]
    unsupported_not_found = unsupported[unsupported["email status"] == "not found"]
    unsupported_unconfirmed = unsupported[unsupported["email status"] == "unconfirmed"]
    supported_errors = concat(
        [
            failed_to_activate,
            error_supported,
            supported_not_found,
        ]
    )
    unsupported_errors = concat(
        [
            error_unsupported,
            unsupported_not_found,
            unsupported_unconfirmed,
        ]
    )
    for data_frame in [
        activated,
        supported_errors,
        unsupported_errors,
        users_not_found,
    ]:
        columns = ["index", "supported"]
        if data_frame is not unsupported_errors:
            columns.append("subaccount")
        data_frame.drop(["index", "supported", "subaccount"], axis=1, inplace=True)
    BASE = COMMAND_PATH / f"{YEAR}"
    if not BASE.exists():
        Path.mkdir(BASE)
    activated_path = BASE / f"{result_path.stem}_ACTIVATED.csv"
    supported_errors_path = BASE / f"{result_path.stem}_SUPPORTED_ERROR.csv"
    unsupported_errors_path = BASE / f"{result_path.stem}_UNSUPPORTED_ERROR.csv"
    users_not_found_path = BASE / f"{result_path.stem}_USERS_NOT_FOUND.csv"
    dynamic_to_csv(activated_path, activated, activated_path.exists())
    dynamic_to_csv(supported_errors_path, supported_errors, new)
    dynamic_to_csv(
        unsupported_errors_path,
        unsupported_errors,
        unsupported_errors_path.exists(),
    )
    dynamic_to_csv(users_not_found_path, users_not_found, new)
    if new:
        drop_duplicate_errors([supported_errors_path, users_not_found_path])
    add_headers_to_empty_files(
        [
            activated_path,
            supported_errors_path,
            unsupported_errors_path,
            users_not_found_path,
        ],
        HEADERS,
    )
    remove(result_path)
    return (
        len(activated.index),
        len(already_active.index),
        len(error_supported.index),
        len(error_unsupported.index),
        len(failed_to_activate.index),
        len(unsupported.index),
        len(supported_not_found.index),
        len(users_not_found.index),
    )


def print_messages(
    total,
    activated,
    already_active,
    error_supported,
    error_unsupported,
    failed_to_activate,
    unsupported,
    supported_not_found,
    user_not_found,
    log_path,
):
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total, 'magenta')} accounts.")
    activated_display = color(activated, "yellow" if not activated else "green")
    echo(
        "- Activated"
        f" {activated_display} supported users with unconfirmed email addresses."
    )
    if already_active:
        echo(
            f"- Found {color(already_active, 'cyan')} supported and unsupported"
            f" {'user' if already_active == 1 else 'users'} with email addresses"
            " already active."
        )
    if supported_not_found:
        echo(
            f"- Found {color(supported_not_found, 'red')} supported"
            f" {'user' if supported_not_found == 1 else 'users'} with no email address."
        )
    if unsupported:
        echo(
            f"- Found {color(unsupported, 'yellow')} unsupported"
            f" {'user' if unsupported == 1 else 'users'} with missing or unconfirmed"
            " email addresses."
        )
    if failed_to_activate:
        message = color(
            f"Failed to activate email(s) for {failed_to_activate} supported"
            f" {'user' if failed_to_activate == 1 else 'users'} with (an) unconfirmed"
            " email address(es).",
            "red",
        )
        log_path_display = color(log_path, "green")
        echo(
            f"- {message}. Affected accounts are recorded in the log file:"
            f" {log_path_display}"
        )
    if user_not_found:
        message = color(
            "Failed to find"
            f" {user_not_found} {'user' if user_not_found == 1 else 'users'}.",
            "red",
        )
        echo(f"- {message}")
    if error_supported:
        echo(
            f"- Encountered an error for {color(error_supported, 'red')} supported"
            f" {'user' if error_supported == 1 else 'users'}."
        )
    if error_unsupported:
        echo(
            "- Encountered an error for"
            f" {color(error_unsupported, 'red')} unsupported"
            f" {'user' if error_unsupported == 1 else 'users'}."
        )
    color("FINISHED", "yellow", True)


def query_data_warehouse(
    login_id: str,
    canvas_user_id: str,
    full_name: str,
    canvas_user: User,
    log_path: Path,
    table: str,
) -> str | None:
    cursor = get_data_warehouse_cursor()
    cursor.execute(
        f"SELECT penn_id, email_address FROM {table} WHERE pennkey = :pennkey",
        pennkey=login_id,
    )
    for _, email in cursor:
        if email:
            return activate_user_email(
                canvas_user_id,
                login_id,
                full_name,
                canvas_user,
                [email.strip()],
                log_path,
            )
    return None


def check_and_activate_emails(
    report: DataFrame,
    total: int,
    user: NamedTuple,
    sub_accounts: list[int],
    log_path: Path,
    use_data_warehouse: bool,
    result_path: Path,
    processed_path: Path,
    processed_errors: list[str],
    processed_errors_path: Path,
    instance: str | Instance,
    verbose: bool,
):
    index, canvas_user_id, login_id, full_name = user
    supported = None
    account = None
    status, canvas_user, emails = is_already_active(user, instance)
    if not canvas_user:
        supported = status
    elif status in {"error", "unconfirmed", "not found"}:
        is_supported, account = check_schools(canvas_user, sub_accounts)
        if is_supported:
            supported = "Y"
            canvas_user_id = user[1]
            if emails and status == "unconfirmed":
                status = activate_user_email(
                    canvas_user_id, login_id, full_name, canvas_user, emails, log_path
                )
            elif use_data_warehouse:
                query_status = query_data_warehouse(
                    login_id,
                    canvas_user_id,
                    full_name,
                    canvas_user,
                    log_path,
                    "employee_general",
                )
                status = query_status if query_status else status
                if not status == "activated":
                    query_status = query_data_warehouse(
                        login_id,
                        canvas_user_id,
                        full_name,
                        canvas_user,
                        log_path,
                        "person_all_v",
                    )
                    status = query_status if query_status else status
        else:
            supported = "N"
    report.at[index, ["email status", "supported", "subaccount"]] = [
        status,
        supported,
        str(account),
    ]
    report.loc[index].to_frame().t.to_csv(result_path, mode="a", header=False)
    if verbose:
        status_color = PRINT_COLOR_MAPS.get(status, "magenta")
        status_display = color(
            f"{'email not found' if status == 'not found' else status}".upper(),
            status_color,
        )
        unsupported_display = ""
        user_display = color(f"{' '.join(full_name.split())} ({login_id})", "magenta")
        if supported == "N":
            unsupported_display = color(" (UNSUPPORTED)", "yellow")
        message = f"{user_display}: {status_display}{unsupported_display}"
        print_item(index, total, message)
    if status in {"activated", "already active"} or supported == "N":
        if canvas_user_id in processed_errors:
            processed_errors_csv = read_csv(processed_errors_path)
            processed_errors_csv = processed_errors_csv[
                processed_errors_csv["canvas user id"] != canvas_user_id
            ]
            processed_errors_csv.to_csv(processed_errors_path, index=False)
        with open(processed_path, "a+", newline="") as processed_file:
            writer(processed_file).writerow(
                [canvas_user_id, login_id, full_name, status, supported]
            )
    elif canvas_user_id not in processed_errors:
        with open(processed_errors_path, "a+", newline="") as processed_file:
            writer(processed_file).writerow(
                [canvas_user_id, login_id, full_name, status, supported]
            )


def email_main(
    instance_name: str | Instance,
    new: bool,
    force: bool,
    force_report: bool,
    clear_processed: bool,
    use_data_warehouse: bool,
    verbose: bool,
):
    if use_data_warehouse and not confirm_global_protect_enabled():
        raise Exit()
    instance = validate_instance_name(instance_name, verbose=True)
    instance_display = format_instance_name(instance)
    RESULT_PATH = COMMAND_PATH / f"{YEAR}_email_result{instance_display}.csv"
    PROCESSED_PATH = PROCESSED / f"{YEAR}_email_processed_users{instance_display}.csv"
    PROCESSED_ERRORS_PATH = (
        PROCESSED / f"{YEAR}_email_processed_errors{instance_display}.csv"
    )
    report_path = get_report(
        "users", CURRENT_YEAR_AND_TERM, force_report, instance, verbose
    )
    handle_clear_processed(clear_processed, [PROCESSED_PATH, PROCESSED_ERRORS_PATH])
    PROCESSED_USERS = get_processed(PROCESSED_PATH, HEADERS)
    PROCESSED_ERRORS = get_processed(PROCESSED_ERRORS_PATH, HEADERS)
    start = get_start_index(force, RESULT_PATH)
    report, total = process_report(report_path, PROCESSED_USERS, PROCESSED_ERRORS, new)
    make_csv_paths(RESULT_PATH, make_index_headers(HEADERS))
    LOG_STEM = (
        f"{YEAR}_email_log_{TODAY_AS_Y_M_D}{instance_display}"
        f"_{datetime.now().strftime('%H_%M_%S')}.csv"
    )
    LOG_PATH = LOGS / LOG_STEM
    make_csv_paths(LOG_PATH, LOG_HEADERS)
    make_skip_message(start, "user")
    main_account = get_account(instance=instance)
    sub_accounts = [
        account.id for account in main_account.get_subaccounts(recursive=True)
    ]
    sub_accounts = [main_account.id] + [sub_accounts]
    echo(") Processing users...")
    if verbose:
        for user in report.itertuples():
            check_and_activate_emails(
                report,
                total,
                user,
                sub_accounts,
                LOG_PATH,
                use_data_warehouse,
                RESULT_PATH,
                PROCESSED_PATH,
                PROCESSED_ERRORS,
                PROCESSED_ERRORS_PATH,
                instance,
                verbose,
            )
    else:
        with progressbar(report.itertuples(), length=total) as progress:
            for user in progress:
                check_and_activate_emails(
                    report,
                    total,
                    user,
                    sub_accounts,
                    LOG_PATH,
                    use_data_warehouse,
                    RESULT_PATH,
                    PROCESSED_PATH,
                    PROCESSED_ERRORS,
                    PROCESSED_ERRORS_PATH,
                    instance,
                    verbose,
                )
    remove_empty_log(LOG_PATH)
    (
        activated,
        already_active,
        error_supported,
        error_unsupported,
        failed_to_activate,
        unsupported,
        supported_not_found,
        user_not_found,
    ) = process_result(RESULT_PATH, new)
    print_messages(
        total,
        activated,
        already_active,
        error_supported,
        error_unsupported,
        failed_to_activate,
        unsupported,
        supported_not_found,
        user_not_found,
        LOG_PATH,
    )
