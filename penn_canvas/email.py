from csv import writer
from pathlib import Path
from shutil import rmtree

from pandas import concat, read_csv
from typer import Exit, echo

from .helpers import (
    TODAY,
    TODAY_AS_Y_M_D,
    YEAR,
    colorize,
    find_sub_accounts,
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
LOG_PATH = LOGS / f"{TODAY_AS_Y_M_D}_email_log.csv"
LOG_HEADERS = ["canvas user id", "email address"]
ACCOUNTS = [
    "99243",
    "99237",
    "128877",
    "99241",
    "99244",
    "99238",
    "99239",
    "131428",
    "99240",
    "132153",
    "82192",
]


def get_subaccounts(canvas):
    return [find_sub_accounts(canvas, account) for account in ACCOUNTS]


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
    data.drop_duplicates(inplace=True)
    data = data.astype("string", copy=False, errors="ignore")
    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, TOTAL


def get_user_emails(user):
    communication_channels = user.get_communication_channels()

    return (channel for channel in communication_channels if channel.type == "email")


def get_email_status(user, email, verbose):
    email_status = email.workflow_state

    if email_status == "active":
        return True
    elif email_status == "unconfirmed":
        return False


def find_unconfirmed_emails(user, canvas, verbose, index):
    user_id = user[1]

    try:
        canvas_user = canvas.get_user(user_id)
    except Exception:
        return False, "user not found"

    emails = get_user_emails(canvas_user)
    email = next(emails, None)

    if email:
        is_active = get_email_status(canvas_user, email, verbose)

        while not is_active:
            next_email = next(emails, None)

            if not next_email:
                return True, "unconfirmed"

            is_active = get_email_status(canvas_user, next_email, verbose)

        if is_active:
            return False, None

    else:
        return True, "not found"


def check_schools(user, sub_accounts, canvas, verbose):
    canvas_user_id = user[1]

    user_id = canvas.get_user(canvas_user_id)
    user_enrollments = user_id.get_courses()

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


def activate_fixable_emails(
    user, canvas, result_path, log_path, include_activated, verbose
):
    canvas_user_id = user[1]
    user_id = canvas.get_user(canvas_user_id)
    emails = get_user_emails(user_id)

    for email in emails:
        address = email.address

        if not LOGS.exists():
            Path.mkdir(LOGS)

        user_info = [user_id, address]

        with open(log_path, "a", newline="") as result:
            writer(result).writerow(user_info)

        email.delete()
        user_id.create_communication_channel(
            communication_channel={"address": address, "type": "email"},
            skip_confirmation=True,
        )

    emails = get_user_emails(user_id)
    email = next(emails, None)
    is_active = get_email_status(user_id, email, False)

    while not is_active:
        next_email = next(emails, None)

        if not next_email:
            if verbose:
                colorize(
                    f"\t* ERROR: failed to activate email(s) for {user_id}!",
                    "red",
                    True,
                )

            return False, "failed to activate"

        is_active = get_email_status(user_id, next_email, False)

    if is_active:
        if verbose:
            colorize(f"\t* Email(s) activated for {user_id}", "green", True)

        log = read_csv(log_path)
        log.drop(index=log.index[-1:], inplace=True)
        log.to_csv(log_path, index=False)

        return True, "auto-activated"


def remove_empty_log(log_path):
    if log_path.is_file():
        log = read_csv(log_path)

        if log.empty:
            echo(") Removing empty log file...")
            rmtree(LOGS, ignore_errors=True)


def process_result(include_fixed, result_path):
    result = read_csv(result_path)

    not_fixable = result[result["supported school(s)"] == "N"]
    not_fixable = not_fixable.sort_values(by=["email status"])
    FIXABLE = result[result["supported school(s)"] == "Y"]
    SUPPORTED_NOT_FOUND = result[
        (result["supported school(s)"] == "Y") & (result["email status"] == "not found")
    ]
    USERS_NOT_FOUND = result[result["email status"] == "ERROR: user not found"]

    fixed = len(FIXABLE[FIXABLE["email status"] == "auto-activated"].index)
    error = len(FIXABLE[FIXABLE["email status"] == "failed to activate"].index)

    result = concat([SUPPORTED_NOT_FOUND, USERS_NOT_FOUND, not_fixable])

    if include_fixed:
        FIXABLE.sort_values(by=["email status"], inplace=True)
        result = concat([FIXABLE, result])
    else:
        ERRORS = FIXABLE[FIXABLE["email status"] == "failed to activate"]
        result = concat([ERRORS, result])

    result.drop("index", axis=1, inplace=True)
    result.to_csv(result_path, index=False)

    unsupported = len(not_fixable.index)
    supported_not_found = len(SUPPORTED_NOT_FOUND.index)
    user_not_found = len(USERS_NOT_FOUND.index)

    return (
        fixed,
        error,
        unsupported,
        supported_not_found,
        user_not_found,
    )


def print_messages(
    total,
    fixed,
    supported_not_found,
    unsupported,
    errors,
    log_path,
    user_not_found,
):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} accounts.")
    echo(
        f"- Activated {fixed if fixed == 0 else colorize(fixed, 'green')} supported users with unconfirmed email"
        " accounts."
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


def email_main(test, include_fixed, verbose, force, clear_processed):
    def check_and_activate_emails(user, canvas, verbose, args):
        index, user_id, login_id, full_name = user
        result_path, log_path, processed_users = args

        if user_id in processed_users:
            status = "already processed"
        else:
            needs_school_check, message = find_unconfirmed_emails(
                user, canvas, verbose, index
            )
            status = "already active"

            if needs_school_check:
                report.at[index, "email status"] = message
                is_supported = check_schools(user, SUB_ACCOUNTS, canvas, verbose)

                if is_supported:
                    report.at[index, "supported school(s)"] = "Y"
                    status = "already active"

                    if message == "unconfirmed":
                        activated, activate_message = activate_fixable_emails(
                            user, canvas, result_path, log_path, include_fixed, verbose
                        )
                        report.at[index, "email status"] = activate_message

                        if activated:
                            status = "activated"
                        else:
                            status = "failed to activate"
                else:
                    report.at[index, "supported school(s)"] = "N"
                    status = "not supported"
            elif message:
                report.at[index, "email status"] = "ERROR: user not found"
                report.at[index, "supported school(s)"] = "ERROR: user not found"
                status = "user not found"

        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            color = {
                "already processed": "yellow",
                "already active": "yellow",
                "activated": "green",
                "failed to activate": "red",
                "not supported": "red",
                "user not found": "red",
            }.get(status)
            status_display = colorize(str(status).upper(), color)
            user_display = colorize(f"{full_name} ({login_id})", "magenta")
            echo(f"- ({index + 1}/{TOTAL}) {user_display}: {status_display}")

        if (
            status == "activated"
            or status == "not supported"
            or status == "already active"
        ) and user_id not in processed_users:
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([user_id])

    RESULT_PATH = (
        RESULTS / f"{YEAR}_email_result_{TODAY_AS_Y_M_D}{'_test' if test else ''}.csv"
    )
    PROCESSED_PATH = (
        PROCESSED / f"email_processed_users_{YEAR}{'_test' if test else ''}.csv"
    )
    report = find_users_report()
    START = get_start_index(force, RESULT_PATH)
    report, TOTAL = cleanup_report(report, START)
    handle_clear_processed(clear_processed, PROCESSED_PATH)
    PROCESSED_USERS = get_processed_users(PROCESSED, PROCESSED_PATH, "user id")
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_csv_paths(LOGS, LOG_PATH, LOG_HEADERS)
    ARGS = RESULT_PATH, LOG_PATH, PROCESSED_USERS
    make_skip_message(START, "user")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    SUB_ACCOUNTS = get_subaccounts(CANVAS)

    echo(") Processing users...")

    toggle_progress_bar(report, check_and_activate_emails, CANVAS, verbose, args=ARGS)
    remove_empty_log(LOG_PATH)
    (
        fixed_count,
        error_count,
        unsupported_count,
        supported_not_found_count,
        user_not_found_count,
    ) = process_result(include_fixed, RESULT_PATH)
    print_messages(
        TOTAL,
        fixed_count,
        supported_not_found_count,
        unsupported_count,
        error_count,
        LOG_PATH,
        user_not_found_count,
    )
