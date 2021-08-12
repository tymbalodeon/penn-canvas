from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path

from pandas import concat, read_csv
from typer import Exit, echo

from .helpers import (
    TODAY,
    TODAY_AS_Y_M_D,
    YEAR,
    colorize,
    get_canvas,
    get_command_paths,
    get_processed_users,
    get_start_index,
    handle_clear_processed,
    make_csv_paths,
    make_skip_message,
    toggle_progress_bar,
)

REPORTS, RESULTS, LOGS, PROCESSED = get_command_paths(
    "email", logs=True, processed=True
)
HEADERS = [
    "canvas user id",
    "login id",
    "full name",
    "email status",
    "supported",
]
INDEX_HEADERS = HEADERS[:]
INDEX_HEADERS.insert(0, "index")
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


def find_users_report():
    echo(") Finding Canvas Provisioning (Users) report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = colorize("- ERROR: Canvas email reports directory not found.", "yellow")
        echo(
            f"{error} \n- Creating one for you at: {colorize(REPORTS, 'green')}\n-"
            " Please add a Canvas Provisioning (Users) report matching today's date to"
            " this directory and then run this script again.\n- (If you need"
            " instructions for generating a Canvas Provisioning report, run this"
            " command with the '--help' flag.)"
        )

        raise Exit(1)
    else:
        CSV_FILES = [report for report in Path(REPORTS).glob("*.csv")]
        TODAYS_REPORT = next(
            (report for report in CSV_FILES if TODAY in report.name), None
        )

        if not TODAYS_REPORT:
            error = colorize(
                "- ERROR: A Canvas Provisioning (Users) CSV report matching today's"
                " date was not found.",
                "yellow",
            )
            echo(
                f"{error}\n- Please add a Canvas (Users) Provisioning report matching"
                " today's date to the following directory and then run this script"
                f" again: {colorize(REPORTS,'green')}\n- (If you need instructions"
                " for generating a Canvas Provisioning report, run this command with"
                " the '--help' flag.)"
            )

            raise Exit(1)
        else:
            return TODAYS_REPORT


def cleanup_report(report, processed_users, processed_errors, new, start=0):
    echo(") Preparing report...")

    data = read_csv(report)
    data = data[["canvas_user_id", "login_id", "full_name"]]
    data.drop_duplicates(subset=["canvas_user_id"], inplace=True)
    data.sort_values("canvas_user_id", ascending=False, inplace=True, ignore_index=True)
    data = data.astype("string", copy=False, errors="ignore")
    data = data[~data["canvas_user_id"].isin(processed_users)]
    already_processed_count = len(processed_users)

    if new:
        data = data[~data["canvas_user_id"].isin(processed_errors)]
        already_processed_count = already_processed_count + len(processed_errors)

    message = colorize(
        f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
        f" {'USER' if already_processed_count == 1 else 'USERS'}...",
        "yellow",
    )
    echo(f") {message}")

    data.reset_index(drop=True, inplace=True)
    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, f"{TOTAL:,}"


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

        if is_active:
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

    return bool(fixable_id)


def activate_user_email(
    canvas_user_id, login_id, full_name, canvas_user, emails, log_path
):
    for email in emails:
        address = email.address
        user_info = [canvas_user_id, login_id, full_name, address]

        with open(log_path, "a", newline="") as result:
            writer(result).writerow(user_info)

        email.delete()
        canvas_user.create_communication_channel(
            communication_channel={"address": address, "type": "email"},
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

    if is_active:
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
    failed_to_activate = supported[supported["email status"] == "failed to activate"]
    supported_not_found = supported[supported["email status"] == "not found"]
    error_supported = supported[supported["email status"] == "error"]
    users_not_found = result[result["email status"] == "user not found"].copy()
    error_unsupported = unsupported[unsupported["email status"] == "error"]
    unsupported_not_found = unsupported[unsupported["email status"] == "not found"]
    unsupported_unconfirmed = unsupported[unsupported["email status"] == "unconfirmed"]

    already_active_count = len(result[result["email status"] == "already active"].index)
    unsupported_count = len(unsupported.index)
    activated_count = len(activated.index)
    failed_to_activate_count = len(failed_to_activate.index)
    supported_not_found_count = len(supported_not_found.index)
    error_supported_count = len(error_supported.index)
    users_not_found_count = len(users_not_found.index)
    error_unsupported_count = len(error_unsupported.index)

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

    activated.drop("index", axis=1, inplace=True)
    supported_errors.drop("index", axis=1, inplace=True)
    unsupported_errors.drop("index", axis=1, inplace=True)
    users_not_found.drop("index", axis=1, inplace=True)
    activated_path = RESULTS / f"{result_path.stem}_ACTIVATED.csv"
    supported_path = RESULTS / f"{result_path.stem}_SUPPORTED_ERROR.csv"
    unsupported_path = RESULTS / f"{result_path.stem}_UNSUPPORTED_ERROR.csv"
    users_not_found_path = RESULTS / f"{result_path.stem}_USERS_NOT_FOUND.csv"

    def dynamic_to_csv(path, dataframe, condition):
        mode = "a" if condition else "w"
        dataframe.to_csv(path, mode=mode, header=condition, index=False)

    dynamic_to_csv(activated_path, activated, activated_path.exists())
    dynamic_to_csv(supported_path, supported_errors, new)
    dynamic_to_csv(unsupported_path, unsupported_errors, unsupported_path.exists())
    dynamic_to_csv(users_not_found_path, users_not_found, new)

    if new:
        for path in [supported_path, users_not_found_path]:
            read_csv(path).drop_duplicates(inplace=True).to_csv(path, index=False)

    remove(result_path)

    return (
        activated_count,
        already_active_count,
        error_supported_count,
        error_unsupported_count,
        failed_to_activate_count,
        unsupported_count,
        supported_not_found_count,
        users_not_found_count,
    )


def print_messages(
    total,
    activated,
    already_active,
    error_supported,
    error_unsupported,
    supported_not_found,
    unsupported,
    failed_to_activate,
    log_path,
    user_not_found,
):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} accounts.")
    activated_display = colorize(activated, "yellow" if not activated else "green")
    echo(
        "- Activated"
        f" {activated_display} supported users with unconfirmed email addresses."
    )

    if already_active > 0:
        echo(
            f"- Found {colorize(already_active, 'cyan')} supported and unsupported"
            f" {'user' if already_active == 1 else 'users'} with email addresses"
            " already active."
        )

    if supported_not_found > 0:
        echo(
            f"- Found {colorize(supported_not_found, 'red')} supported"
            f" {'user' if supported_not_found == 1 else 'users'} with no email address."
        )

    if unsupported > 0:
        echo(
            f"- Found {colorize(unsupported, 'yellow')} unsupported"
            f" {'user' if unsupported == 1 else 'users'} with missing or unconfirmed"
            " email addresses."
        )

    if failed_to_activate > 0:
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

    if user_not_found > 0:
        message = colorize(
            "Failed to find"
            f" {user_not_found} {'user' if user_not_found == 1 else 'users'}.",
            "red",
        )
        echo(f"- {message}")

    if error_supported > 0:
        echo(
            f"- Encountered an error for {colorize(error_supported, 'red')} supported"
            f" {'user' if error_supported == 1 else 'users'}."
        )

    if error_unsupported > 0:
        echo(
            "- Encountered an error for"
            f" {colorize(error_unsupported, 'red')} unsupported"
            f" {'user' if error_unsupported == 1 else 'users'}."
        )

    colorize("FINISHED", "yellow", True)


def email_main(test, verbose, new, force, clear_processed):
    def check_and_activate_emails(user, canvas, verbose, args):
        index, canvas_user_id, login_id, full_name = user

        status = None
        supported = None

        status, canvas_user, emails = is_already_active(user, canvas, verbose, index)

        if status == "error" or status == "unconfirmed" or status == "not found":
            is_supported = check_schools(canvas_user, SUB_ACCOUNTS, canvas, verbose)

            if is_supported:
                supported = "Y"
                status = "not found"

                if status == "unconfirmed":
                    activated = activate_user_email(
                        user[1],
                        login_id,
                        full_name,
                        canvas_user,
                        emails,
                        LOG_PATH,
                    )
                    status = activated
            else:
                supported = "N"
        elif status == "user not found":
            supported = status = "user not found"

        report.at[index, ["email status", "supported"]] = [
            status,
            supported,
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

        if status == "activated" or supported == "N" or status == "already active":
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow(
                    [canvas_user_id, login_id, full_name, status, supported]
                )
        elif canvas_user_id not in PROCESSED_ERRORS:
            with open(PROCESSED_ERRORS_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow(
                    [canvas_user_id, login_id, full_name, status, supported]
                )

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
    report = find_users_report()
    PROCESSED_USERS = get_processed_users(PROCESSED, PROCESSED_PATH, HEADERS)
    PROCESSED_ERRORS = get_processed_users(PROCESSED, PROCESSED_ERRORS_PATH, HEADERS)
    START = get_start_index(force, RESULT_PATH, RESULTS)
    report, TOTAL = cleanup_report(
        report, PROCESSED_USERS, PROCESSED_ERRORS, new, START
    )
    make_csv_paths(RESULTS, RESULT_PATH, INDEX_HEADERS)
    LOG_PATH = LOGS / LOG_STEM
    make_csv_paths(LOGS, LOG_PATH, LOG_HEADERS)
    make_skip_message(START, "user")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    SUB_ACCOUNTS = get_sub_accounts(CANVAS)

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
        supported_not_found,
        unsupported,
        failed_to_activate,
        LOG_PATH,
        user_not_found,
    )
