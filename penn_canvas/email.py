from csv import writer
from datetime import datetime
from pathlib import Path
from shutil import rmtree

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
    "index",
    "canvas user id",
    "login id",
    "full name",
    "email status",
    "supported school(s)",
]
LOG_HEADERS = ["canvas user id", "name", "email address"]
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


def cleanup_report(report, start=0):
    echo(") Preparing report...")

    data = read_csv(report)
    data = data[["canvas_user_id", "login_id", "full_name"]]
    data.drop_duplicates(subset=["canvas_user_id"], inplace=True)
    data.sort_values("canvas_user_id", ascending=False, inplace=True, ignore_index=True)
    data = data.astype("string", copy=False, errors="ignore")
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
        return False, "user not found", canvas_user, emails

    try:
        emails = get_user_emails(canvas_user)
    except Exception:
        return True, "error", canvas_user, emails

    emails_iterator = iter(emails)
    email = next(emails_iterator, None)

    if email:
        is_active = get_email_status(email)

        while not is_active:
            next_email = next(emails_iterator, None)

            if not next_email:
                return True, "unconfirmed", canvas_user, emails

            is_active = get_email_status(next_email)

        if is_active:
            return False, "already active", canvas_user, emails
    else:
        return True, "not found", canvas_user, emails


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


def activate_user_email(canvas_user_id, canvas_user, emails, log_path):
    for email in emails:
        address = email.address
        user_info = [canvas_user_id, canvas_user.name, address]

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
            return False, "failed to activate"

        is_active = get_email_status(next_email)

    if is_active:
        log = read_csv(log_path)
        log.drop(index=log.index[-1:], inplace=True)
        log.to_csv(log_path, index=False)

        return True, "activated"


def remove_empty_log(log_path):
    if log_path.is_file() and read_csv(log_path).empty:
        echo(") Removing empty log file...")
        rmtree(LOGS, ignore_errors=True)


def process_result(include_activated, result_path):
    result = read_csv(result_path)

    ALREADY_PROCESSED_COUNT = len(
        result[result["email status"] == "already processed"].index
    )
    unsupported = result[result["supported school(s)"] == "N"]
    unsupported = unsupported.sort_values(by=["email status"])
    SUPPORTED = result[result["supported school(s)"] == "Y"]
    SUPPORTED_NOT_FOUND = result[
        (result["supported school(s)"] == "Y") & (result["email status"] == "not found")
    ]
    USERS_NOT_FOUND = result[result["email status"] == "user not found"]
    activated_count = len(SUPPORTED[SUPPORTED["email status"] == "activated"].index)
    already_active_count = len(result[result["email status"] == "already active"].index)
    failed_to_activate_count = len(
        SUPPORTED[SUPPORTED["email status"] == "failed to activate"].index
    )
    unsupported_count = len(unsupported.index)
    supported_not_found_count = len(SUPPORTED_NOT_FOUND.index)
    users_not_found_count = len(USERS_NOT_FOUND.index)
    FAILED_TO_ACTIVATE = SUPPORTED[SUPPORTED["email status"] == "failed to activate"]
    result = concat(
        [FAILED_TO_ACTIVATE, SUPPORTED_NOT_FOUND, USERS_NOT_FOUND, unsupported]
    )
    result.drop("index", axis=1, inplace=True)

    if include_activated:
        SUPPORTED.sort_values(by=["email status"], inplace=True)
        fixed_stem = (
            f"{result_path.stem}_{datetime.now().strftime('%H_%M_%S')}"
            "_fixed_COMPLETE.csv"
        )
        fixed_path = RESULTS / fixed_stem
        result.to_csv(fixed_path, index=False)

    result.to_csv(result_path, index=False)
    final_path = (
        RESULTS
        / f"{result_path.stem}_{datetime.now().strftime('%H_%M_%S')}_COMPLETE.csv"
    )
    result_path.rename(final_path)

    return (
        ALREADY_PROCESSED_COUNT,
        activated_count,
        already_active_count,
        failed_to_activate_count,
        unsupported_count,
        supported_not_found_count,
        users_not_found_count,
    )


def print_messages(
    total,
    already_processed,
    activated,
    already_active,
    supported_not_found,
    unsupported,
    errors,
    log_path,
    user_not_found,
):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} accounts.")
    activated_display = colorize(activated, "yellow" if not activated else "green")
    echo(
        "- Activated"
        f" {activated_display} supported users with unconfirmed email accounts."
    )

    if already_processed > 0:
        echo(
            f"- Skipped {colorize(already_processed, 'yellow')} users already"
            " processed."
        )

    if already_active > 0:
        echo(
            f"- Found {colorize(already_active, 'cyan')} supported and unsupported"
            " users with email accounts already active."
        )

    if supported_not_found > 0:
        echo(
            f"- Found {colorize(supported_not_found, 'red')} supported users with no"
            " email account."
        )

    if unsupported > 0:
        echo(
            f"- Found {colorize(unsupported, 'yellow')} unsupported users with missing"
            " or unconfirmed email accounts."
        )

    if errors > 0:
        message = colorize(
            f"Failed to activate email(s) for {errors} supported users with (an)"
            " unconfirmed email account(s).",
            "red",
        )
        log_path_display = colorize(log_path, "green")
        echo(
            f"- {message}. Affected accounts are recorded in the log file:"
            f" {log_path_display}"
        )

    if user_not_found > 0:
        message = colorize(f"Failed to find {user_not_found} users.", "red")
        echo(f"- {message}")

    colorize("FINISHED", "yellow", True)


def email_main(test, include_activated, verbose, force, clear_processed):
    def check_and_activate_emails(user, canvas, verbose, args):
        index, user_id, login_id, full_name = user
        result_path, log_path, processed_users = args

        status = None
        supported = None

        if user_id in processed_users:
            status = "already processed"
        else:
            needs_school_check, message, canvas_user, emails = is_already_active(
                user, canvas, verbose, index
            )
            status = message

            if needs_school_check:
                is_supported = check_schools(canvas_user, SUB_ACCOUNTS, canvas, verbose)

                if is_supported:
                    supported = "Y"
                    status = "not found"

                    if message == "unconfirmed":
                        activated, activate_message = activate_user_email(
                            user[1],
                            canvas_user,
                            emails,
                            log_path,
                        )
                        status = activate_message
                else:
                    supported = "N"
                    status = "unsupported"
            elif message == "user not found":
                supported = status = "user not found"

        report.at[index, ["email status", "supported school(s)"]] = [
            status,
            supported,
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            color = PRINT_COLOR_MAPS.get(status, "magenta")
            status_display = colorize(str(status).upper(), color)
            user_display = colorize(
                f"{' '.join(full_name.split())} ({login_id})", "magenta"
            )

            if status == "unsupported":
                email_status_display = colorize(f" ({str(message).upper()})", color)

            echo(
                f"- ({(index + 1):,}/{TOTAL}) {user_display}:"
                f" {status_display}"
                f"{email_status_display if status == 'unsupported' else ''}"
            )

        if (
            status == "activated"
            or status == "unsupported"
            or status == "already active"
        ) and user_id not in processed_users:
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([user_id, status])

    RESULT_PATH = (
        RESULTS / f"{YEAR}_email_result_{TODAY_AS_Y_M_D}{'_test' if test else ''}.csv"
    )
    PROCESSED_PATH = (
        PROCESSED / f"{YEAR}_email_processed_users{'_test' if test else ''}.csv"
    )
    LOG_PATH = LOGS / f"{YEAR}_email_log_{TODAY_AS_Y_M_D}{'_test' if test else ''}.csv"
    report = find_users_report()
    START = get_start_index(force, RESULT_PATH, RESULTS)
    report, TOTAL = cleanup_report(report, START)
    handle_clear_processed(clear_processed, PROCESSED_PATH)
    PROCESSED_USERS = get_processed_users(
        PROCESSED, PROCESSED_PATH, ["user id", "status"]
    )
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_csv_paths(LOGS, LOG_PATH, LOG_HEADERS)
    ARGS = RESULT_PATH, LOG_PATH, PROCESSED_USERS
    make_skip_message(START, "user")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    SUB_ACCOUNTS = get_sub_accounts(CANVAS)

    if verbose:
        PRINT_COLOR_MAPS = {
            "already processed": "yellow",
            "already active": "cyan",
            "activated": "green",
            "failed to activate": "red",
            "unsupported": "yellow",
            "user not found": "red",
            "not found": "red",
        }

    echo(") Processing users...")

    toggle_progress_bar(report, check_and_activate_emails, CANVAS, verbose, args=ARGS)
    remove_empty_log(LOG_PATH)
    (
        already_processed,
        activated,
        already_active,
        error,
        unsupported,
        supported_not_found,
        user_not_found,
    ) = process_result(include_activated, RESULT_PATH)
    print_messages(
        TOTAL,
        already_processed,
        activated,
        already_active,
        supported_not_found,
        unsupported,
        error,
        LOG_PATH,
        user_not_found,
    )
