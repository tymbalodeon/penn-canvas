import shutil
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    colorize,
    colorize_path,
    find_sub_accounts,
    get_canvas,
    get_command_paths,
    make_results_paths,
    toggle_progress_bar,
)

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS, LOGS = get_command_paths("email", True)
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_email_result.csv"
HEADERS = ["index", "canvas user id", "email status", "supported school(s)"]
LOG_PATH = LOGS / f"{TODAY_AS_Y_M_D}_email_log.csv"
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


def get_sub_accounts(canvas):
    SUB_ACCOUNTS = list()

    for account in ACCOUNTS:
        SUB_ACCOUNTS += find_sub_accounts(canvas, account)

    return SUB_ACCOUNTS


def find_users_report():
    typer.echo(") Finding users report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = typer.style(
            "- ERROR: Canvas email reports directory not found.", fg=typer.colors.YELLOW
        )
        typer.echo(
            f"{error} \n- Creating one for you at: {colorize_path(str(REPORTS))}\n-"
            " Please add a Canvas Users Provisioning report matching today's date to"
            " this directory and then run this script again.\n- (If you need"
            " instructions for generating a Canvas Provisioning report, run this"
            " command with the '--help' flag.)"
        )
        raise typer.Exit(1)
    else:
        TODAYS_REPORT = ""
        CSV_FILES = Path(REPORTS).glob("*.csv")

        for report in CSV_FILES:
            if TODAY in report.name:
                TODAYS_REPORT = report

        if not TODAYS_REPORT:
            typer.secho(
                "- ERROR: A Canvas Provisioning Users CSV report matching today's date"
                " was not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                "- Please add a Canvas Users Provisioning report matching today's date"
                " to the following directory and then run this script again:"
                f" {colorize_path(str(REPORTS))}\n- (If you need instructions for"
                " generating a Canvas Provisioning report, run this command with the"
                " '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            return TODAYS_REPORT


def cleanup_report(report, start=0):
    typer.echo(") Removing unused columns...")

    data = pandas.read_csv(report)
    data = data[["canvas_user_id"]]
    data.drop_duplicates(inplace=True)
    data = data.astype("string", copy=False)

    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def get_user_emails(user):
    communication_channels = user.get_communication_channels()
    return filter(lambda channel: channel.type == "email", communication_channels)


def get_email_status(user_id, email, verbose):
    email_status = email.workflow_state

    if email_status == "active":
        if verbose:
            status = typer.style(f"{email_status}", fg=typer.colors.GREEN)
            typer.echo(f"- Email status is {status} for user {user_id}")
        return True
    elif email_status == "unconfirmed":
        return False


def find_unconfirmed_emails(user, canvas, verbose):
    user_id = user[1]
    canvas_user = canvas.get_user(user_id)
    emails = get_user_emails(canvas_user)
    email = next(emails, None)

    if email:
        is_active = get_email_status(user_id, email, verbose)

        while not is_active:
            next_email = next(emails, None)
            if not next_email:
                if verbose:
                    status = typer.style("UNCONFIRMED", fg=typer.colors.YELLOW)
                    typer.echo(f"- Email status is {status} for user {user_id}")
                return True, "unconfirmed"
                break
            is_active = get_email_status(user_id, next_email, verbose)

        if is_active:
            return False, None

    else:
        if verbose:
            status = typer.style("NOT FOUND", fg=typer.colors.YELLOW)
            typer.echo(f"- Email status is {status} for user {user_id}")
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

    account_ids = map(get_account_id, user_enrollments)
    fixable_id = next(
        filter(lambda account: account in sub_accounts, account_ids), None
    )

    if fixable_id:
        if verbose:
            supported = typer.style("supported", fg=typer.colors.GREEN)
            typer.echo(f"\t* Enrollment status for user {canvas_user_id}: {supported}")
        return True
    else:
        if verbose:
            supported = typer.style("UNSUPPORTED", fg=typer.colors.YELLOW)
            typer.echo(f"\t* Enrollment status for user {canvas_user_id}: {supported}")
        return False


def activate_fixable_emails(
    user, canvas, result_path, log_path, include_fixed, verbose
):
    canvas_user_id = user[1]
    user_id = canvas.get_user(canvas_user_id)
    emails = get_user_emails(user_id)

    for email in emails:
        address = email.address

        if not LOGS.exists():
            Path.mkdir(LOGS)

        user_info = pandas.DataFrame(
            [[user_id, address]], columns=["canvas user id", "address"]
        )
        user_info.to_csv(log_path, mode="a", index=False)

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
                typer.secho(
                    f"- ERROR: failed to activate email(s) for user {user_id}!",
                    fg=typer.colors.RED,
                )
            return False, "failed to activate"
            break
        is_active = get_email_status(user_id, next_email, False)

    if is_active:
        if verbose:
            typer.echo(f"- Email(s) activated for user: {user_id}")
        return True, "auto-activate"
        log = pandas.read_csv(log_path)
        log.drop(index=log.index[-1:], inplace=True)
        log.to_csv(log_path)


def remove_empty_log(log_path):
    if log_path.is_file():
        log = pandas.read_csv(log_path)
        if log.empty:
            typer.echo(") Removing empty log file...")
            shutil.rmtree(LOGS, ignore_errors=True)


def process_result(include_fixed):
    result = pandas.read_csv(RESULT_PATH)

    if "supported school(s)" in result.columns:
        NOT_FIXABLE = result[result["supported school(s)"] == "N"]
        FIXABLE = result[
            (result["supported school(s)"] == "Y")
            & (result["email status"] == "unconfirmed")
        ]
        SUPPORTED_NOT_FOUND = result[
            (result["supported school(s)"] == "Y")
            & (result["email status"] == "not found")
        ]
    else:
        NOT_FIXABLE = result
        FIXABLE = result
        SUPPORTED_NOT_FOUND = result

    if "email status" in FIXABLE.columns:
        fixed = len(FIXABLE[FIXABLE["email status"] == "auto-activated"].index)
        error = len(FIXABLE[FIXABLE["email status"] == "failed to activate"].index)
    else:
        fixed = 0
        error = 0

    if include_fixed:
        if "email status" in FIXABLE.columns:
            FIXABLE.sort_values(by=["email status"])
        DATA_FRAMES = [FIXABLE, SUPPORTED_NOT_FOUND, NOT_FIXABLE]
    else:
        if "email status" in FIXABLE.columns:
            ERRORS = FIXABLE[FIXABLE["email status"] == "failed to activate"]
        else:
            ERRORS = FIXABLE
        DATA_FRAMES = [ERRORS, SUPPORTED_NOT_FOUND, NOT_FIXABLE]

    result = pandas.concat(DATA_FRAMES)
    result.drop("index", axis=1, inplace=True)
    result.to_csv(RESULT_PATH, index=False)

    fixed_count = str(fixed)
    error_count = str(error)
    unsupported_count = str(len(NOT_FIXABLE.index))
    supported_not_found_count = str(len(SUPPORTED_NOT_FOUND.index))

    return fixed_count, error_count, unsupported_count, supported_not_found_count


def print_messages(total, fixed, supported_not_found, unsupported, errors, log_path):
    typer.echo(f"- Processed {colorize(total)} accounts.")
    typer.echo(
        f"- Activated {colorize(fixed)} supported users with unconfirmed email"
        " accounts."
    )
    typer.echo(
        f"- Found {colorize(supported_not_found)} supported users with no email"
        " account."
    )
    typer.echo(
        f"- Found {colorize(unsupported)} unsupported users with missing or unconfirmed"
        " email accounts."
    )
    if errors != "0":
        typer.secho(
            f"- Failed to activate email(s) for {errors} supported users with (an)"
            " unconfirmed email account(s). Affected accounts are recorded in the log"
            f" file: {log_path}",
            fg=typer.colors.RED,
        )
    typer.echo("FINISHED")


def email_main(test, include_fixed, verbose):
    CANVAS = get_canvas(test)
    report = find_users_report()
    report, TOTAL = cleanup_report(report)
    make_results_paths(RESULTS, RESULT_PATH, HEADERS)
    SUB_ACCOUNTS = get_sub_accounts(CANVAS)

    def check_and_activate_emails(user, canvas, verbose, options):
        index = user[0]
        result_path, log_path = options
        needs_support_check, message = find_unconfirmed_emails(user, canvas, verbose)

        if needs_support_check:
            report.at[index, "email status"] = message
            is_supported = check_schools(user, SUB_ACCOUNTS, canvas, verbose)
            if is_supported:
                report.at[index, "supported school(s)"] = "Y"
                if message == "unconfirmed":
                    activated, message = activate_fixable_emails(
                        user, canvas, result_path, log_path, include_fixed, verbose
                    )
            else:
                report.at[index, "supported school(s)"] = "N"

            report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)
        else:
            report.drop(index=index, inplace=True)
            report.reset_index(drop=True)

    OPTIONS = RESULT_PATH, LOG_PATH
    typer.echo(") Processing users...")
    toggle_progress_bar(
        report, check_and_activate_emails, CANVAS, verbose, options=OPTIONS, index=True
    )
    remove_empty_log(LOG_PATH)

    (
        fixed_count,
        error_count,
        unsupported_count,
        supported_not_found_count,
    ) = process_result(include_fixed)

    print_messages(
        TOTAL,
        fixed_count,
        supported_not_found_count,
        unsupported_count,
        error_count,
        LOG_PATH,
    )
