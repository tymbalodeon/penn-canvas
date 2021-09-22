from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path

from cx_Oracle import connect
from pandas import concat, read_csv
from typer import echo, confirm

from .helpers import (
    TODAY_AS_Y_M_D,
    YEAR,
    add_headers_to_empty_files,
    colorize,
    drop_duplicate_errors,
    dynamic_to_csv,
    find_input,
    get_canvas,
    get_command_paths,
    get_data_warehouse_config,
    get_processed,
    get_start_index,
    handle_clear_processed,
    init_data_warehouse,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    process_input,
    toggle_progress_bar,
)

COMMAND = "Email"
INPUT_FILE_NAME = "Canvas Provisioning (Users) report"
REPORTS, RESULTS, LOGS, PROCESSED = get_command_paths(
    COMMAND, logs=True, processed=True
)
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


def cleanup_data(data, args):
    processed_users, processed_errors, new = args

    data.drop_duplicates(subset=["canvas_user_id"], inplace=True)
    data.sort_values("canvas_user_id", ascending=False, inplace=True, ignore_index=True)
    data = data.astype("string", copy=False, errors="ignore")
    data = data[~data["canvas_user_id"].isin(processed_users)]
    already_processed_count = len(processed_users)

    if new:
        data = data[~data["canvas_user_id"].isin(processed_errors)]
        already_processed_count = already_processed_count + len(processed_errors)

    if already_processed_count:
        message = colorize(
            f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
            f" {'USER' if already_processed_count == 1 else 'USERS'}...",
            "yellow",
        )
        echo(f") {message}")

    return data


def find_sub_accounts(canvas, account_id):
    ACCOUNT = canvas.get_account(account_id)
    sub_accounts = ACCOUNT.get_subaccounts(recursive=True)
    ACCOUNTS = [account_id]
    ACCOUNTS.extend([account.id for account in sub_accounts])

    return ACCOUNTS


def get_sub_accounts(canvas):
    return [
        account
        for accounts in (find_sub_accounts(canvas, account) for account in ACCOUNTS)
        for account in accounts
    ]


def get_user_emails(user):
    communication_channels = user.get_communication_channels()

    return [channel for channel in communication_channels if channel.type == "email"]


def get_email_status(email):
    return email.workflow_state == "active"


def is_already_active(user, canvas, verbose, index):
    user_id = user[1]

    canvas_user = None
    emails = None

    try:
        canvas_user = canvas.get_user(user_id)
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


def check_schools(canvas_user, sub_accounts, canvas, verbose):
    user_enrollments = canvas_user.get_courses()

    def get_account_id(course):
        try:
            return course.account_id
        except Exception:
            return ""

    account_ids = [get_account_id(course) for course in user_enrollments]
    fixable_id = next(
        (account for account in account_ids if account in sub_accounts), None
    )

    return bool(fixable_id), account_ids[0] if len(account_ids) else None


def activate_user_email(
    canvas_user_id, login_id, full_name, canvas_user, emails, log_path
):
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

    emails = iter(get_user_emails(canvas_user))
    email = next(emails, None)
    is_active = get_email_status(email)

    while not is_active:
        next_email = next(emails, None)

        if not next_email:
            return "failed to activate"

        is_active = get_email_status(next_email)

    log = read_csv(log_path)
    log.drop(index=log.index[-1:], inplace=True)
    log.to_csv(log_path, index=False)

    return "activated"


def remove_empty_log(log_path):
    if log_path.is_file() and read_csv(log_path).empty:
        echo(") Removing empty log file...")
        remove(log_path)


def process_result(result_path, processed_path, new):
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

    BASE = RESULTS / f"{YEAR}"

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
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} accounts.")
    activated_display = colorize(activated, "yellow" if not activated else "green")
    echo(
        "- Activated"
        f" {activated_display} supported users with unconfirmed email addresses."
    )

    if already_active:
        echo(
            f"- Found {colorize(already_active, 'cyan')} supported and unsupported"
            f" {'user' if already_active == 1 else 'users'} with email addresses"
            " already active."
        )

    if supported_not_found:
        echo(
            f"- Found {colorize(supported_not_found, 'red')} supported"
            f" {'user' if supported_not_found == 1 else 'users'} with no email address."
        )

    if unsupported:
        echo(
            f"- Found {colorize(unsupported, 'yellow')} unsupported"
            f" {'user' if unsupported == 1 else 'users'} with missing or unconfirmed"
            " email addresses."
        )

    if failed_to_activate:
        message = colorize(
            f"Failed to activate email(s) for {failed_to_activate} supported"
            f" {'user' if failed_to_activate == 1 else 'users'} with (an) unconfirmed"
            " email address(es).",
            "red",
        )
        log_path_display = colorize(log_path, "green")
        echo(
            f"- {message}. Affected accounts are recorded in the log file:"
            f" {log_path_display}"
        )

    if user_not_found:
        message = colorize(
            "Failed to find"
            f" {user_not_found} {'user' if user_not_found == 1 else 'users'}.",
            "red",
        )
        echo(f"- {message}")

    if error_supported:
        echo(
            f"- Encountered an error for {colorize(error_supported, 'red')} supported"
            f" {'user' if error_supported == 1 else 'users'}."
        )

    if error_unsupported:
        echo(
            "- Encountered an error for"
            f" {colorize(error_unsupported, 'red')} unsupported"
            f" {'user' if error_unsupported == 1 else 'users'}."
        )

    colorize("FINISHED", "yellow", True)


def email_main(test, verbose, new, force, clear_processed, no_data_warehouse):
    def check_and_activate_emails(user, canvas, verbose):
        index, canvas_user_id, login_id, full_name = user

        supported = None
        account = None

        status, canvas_user, emails = is_already_active(user, canvas, verbose, index)

        if status == "error" or status == "unconfirmed" or status == "not found":
            is_supported, account = check_schools(
                canvas_user, SUB_ACCOUNTS, canvas, verbose
            )

            if is_supported:
                supported = "Y"
                canvas_user_id = user[1]

                if status == "unconfirmed":
                    status = activate_user_email(
                        canvas_user_id,
                        login_id,
                        full_name,
                        canvas_user,
                        emails,
                        LOG_PATH,
                    )
                elif status == "not found" and not no_data_warehouse:
                    cursor = connect(
                        DATA_WAREHOUSE_USER,
                        DATA_WAREHOUSE_PASSWORD,
                        DATA_WAREHOUSE_DSN,
                    ).cursor()
                    cursor.execute(
                        """
                        SELECT
                            penn_id, email_address
                        FROM
                            employee_general
                        WHERE
                            pennkey = :pennkey
                        """,
                        pennkey=login_id,
                    )

                    for penn_id, email in cursor:
                        if email:
                            status = activate_user_email(
                                canvas_user_id,
                                login_id,
                                full_name,
                                canvas_user,
                                [email.strip()],
                                LOG_PATH,
                            )
                    if not status == "activated":
                        cursor = connect(
                            DATA_WAREHOUSE_USER,
                            DATA_WAREHOUSE_PASSWORD,
                            DATA_WAREHOUSE_DSN,
                        ).cursor()
                        cursor.execute(
                            """
                            SELECT
                                penn_id, email_address
                            FROM
                                person_all_v
                            WHERE
                                pennkey = :pennkey
                            """,
                            pennkey=login_id,
                        )

                        for penn_id, email in cursor:
                            if email:
                                status = activate_user_email(
                                    canvas_user_id,
                                    login_id,
                                    full_name,
                                    canvas_user,
                                    [email.strip()],
                                    LOG_PATH,
                                )
            else:
                supported = "N"
        elif status == "user not found":
            supported = status = "user not found"

        report.at[index, ["email status", "supported", "subaccount"]] = [
            status,
            supported,
            str(account),
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            color = PRINT_COLOR_MAPS.get(status, "magenta")
            status_display = colorize(
                f"{'email not found' if status == 'not found' else status}".upper(),
                color,
            )
            unsupported_display = ""
            user_display = colorize(
                f"{' '.join(full_name.split())} ({login_id})", "magenta"
            )

            if supported == "N":
                unsupported_display = colorize(" (UNSUPPORTED)", "yellow")

            echo(
                f"- ({(index + 1):,}/{TOTAL}) {user_display}:"
                f" {status_display}{unsupported_display}"
            )

        if status in {"activated", "already active"} or supported == "N":
            if canvas_user_id in PROCESSED_ERRORS:
                processed_errors_csv = read_csv(PROCESSED_ERRORS_PATH)
                processed_errors_csv = processed_errors_csv[
                    processed_errors_csv["canvas user id"] != canvas_user_id
                ]
                processed_errors_csv.to_csv(PROCESSED_ERRORS_PATH, index=False)

            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow(
                    [canvas_user_id, login_id, full_name, status, supported]
                )
        elif canvas_user_id not in PROCESSED_ERRORS:
            with open(PROCESSED_ERRORS_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow(
                    [canvas_user_id, login_id, full_name, status, supported]
                )

    global_protect_enabled = confirm("HAVE YOU ENABLED GLOBALPROTECT VPN?")

    if not global_protect_enabled:
        return

    RESULT_PATH = RESULTS / f"{YEAR}_email_result{'_test' if test else ''}.csv"
    PROCESSED_PATH = (
        PROCESSED / f"{YEAR}_email_processed_users{'_test' if test else ''}.csv"
    )
    PROCESSED_ERRORS_PATH = (
        PROCESSED / f"{YEAR}_email_processed_errors{'_test' if test else ''}.csv"
    )
    LOG_STEM = (
        f"{YEAR}_email_log_{TODAY_AS_Y_M_D}{'_test' if test else ''}"
        f"_{datetime.now().strftime('%H_%M_%S')}.csv"
    )
    handle_clear_processed(clear_processed, [PROCESSED_PATH, PROCESSED_ERRORS_PATH])
    reports, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS
    )
    PROCESSED_USERS = get_processed(PROCESSED, PROCESSED_PATH, HEADERS)
    PROCESSED_ERRORS = get_processed(PROCESSED, PROCESSED_ERRORS_PATH, HEADERS)
    START = get_start_index(force, RESULT_PATH, RESULTS)
    cleanup_data_args = (PROCESSED_USERS, PROCESSED_ERRORS, new)
    CLEANUP_HEADERS = [header.replace(" ", "_") for header in HEADERS[:3]]
    report, TOTAL = process_input(
        reports,
        INPUT_FILE_NAME,
        REPORTS,
        please_add_message,
        CLEANUP_HEADERS,
        cleanup_data,
        missing_file_message,
        cleanup_data_args,
        START,
    )
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    LOG_PATH = LOGS / LOG_STEM
    make_csv_paths(LOGS, LOG_PATH, LOG_HEADERS)
    make_skip_message(START, "user")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    SUB_ACCOUNTS = get_sub_accounts(CANVAS)
    (
        DATA_WAREHOUSE_USER,
        DATA_WAREHOUSE_PASSWORD,
        DATA_WAREHOUSE_DSN,
    ) = get_data_warehouse_config()
    init_data_warehouse()

    if verbose:
        PRINT_COLOR_MAPS = {
            "already active": "cyan",
            "activated": "green",
            "failed to activate": "red",
            "unconfirmed": "yellow",
            "user not found": "red",
            "not found": "red",
            "error": "red",
        }

    echo(") Processing users...")

    toggle_progress_bar(report, check_and_activate_emails, CANVAS, verbose)
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
    ) = process_result(RESULT_PATH, PROCESSED_PATH, new)
    print_messages(
        TOTAL,
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
