import json
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .canvas_shared import find_sub_accounts, get_canvas, get_command_paths

REPORTS, RESULTS, LOGS = get_command_paths("email", True)
USERS_REPORT = REPORTS / "users.csv"
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


def find_users_report():
    typer.echo(") Finding users report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        typer.echo(
            "\tCanvas email reports directory not found. Creating one for you at:"
            f" {REPORTS}\n\tPlease add a Canvas Users Provisioning report to this"
            " directory and then run this script again.\n\t(If you need instructions"
            " for generating a Canvas Provisioning report, run this command with the"
            " '--help' flag.)"
        )
        raise typer.Exit(1)
    else:
        if not USERS_REPORT.exists():
            typer.secho(
                "- ERROR: A Canvas Provisioning Users CSV report was not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                "- Please add a Canvas Users Provisioning report to this directory"
                " and then run this script again.\n- (If you need instructions for"
                " generating a Canvas Provisioning report, run this command with the"
                " '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            DATE_CREATED = datetime.fromtimestamp(
                USERS_REPORT.stat().st_birthtime
            ).strftime("%Y_%m_%d")
            DATED_REPORT = REPORTS / f"{DATE_CREATED}_{USERS_REPORT.name}"
            RESULT_PATH = RESULTS / f"{DATE_CREATED}_results.csv"
            LOG_PATH = LOGS / f"{DATE_CREATED}_logs.json"

            return USERS_REPORT.rename(DATED_REPORT), RESULT_PATH, LOG_PATH


def cleanup_report(report):
    typer.echo(") Removing unused columns...")
    data = pandas.read_csv(report)
    data = data[["canvas_user_id"]]
    data.drop_duplicates(inplace=True)
    data = data.astype("string", copy=False)

    TOTAL = str(len(data.index))

    return data, TOTAL


def get_user_emails(user):
    communication_channels = user.get_communication_channels()
    return filter(lambda channel: channel.type == "email", communication_channels)


def get_email_status(user_id, email, verbose):
    email_status = email.workflow_state

    if email_status == "active":
        if verbose:
            status = typer.style(f"{email_status}", fg=typer.colors.GREEN)
            typer.echo(f"- Email status is {status} for user: {user_id}")
        return True
    elif email_status == "unconfirmed":
        return False


def find_unconfirmed_emails(data, canvas, verbose):
    typer.echo(") Finding unconfirmed emails...")
    ROWS = data.itertuples()

    def get_email_status_list(row):
        index, user_id = row
        canvas_user = canvas.get_user(user_id)
        emails = get_user_emails(canvas_user)
        email = next(emails, None)

        if email:
            is_active = get_email_status(user_id, email, verbose)

            while not is_active:
                next_email = next(emails, None)
                if not next_email:
                    if verbose:
                        status = typer.style("unconfirmed", fg=typer.colors.YELLOW)
                        typer.echo(f"- Email status is {status} for user: {user_id}")
                    data.at[index, "email status"] = "unconfirmed"
                    break
                is_active = get_email_status(user_id, next_email, verbose)

            if is_active:
                data.drop(index=index, inplace=True)

        else:
            if verbose:
                error = typer.style("No email found for user:", fg=typer.colors.YELLOW)
                typer.echo(f"- {error} {user_id}")
            data.at[index, "email status"] = "not found"

    if verbose:
        for row in ROWS:
            get_email_status_list(row)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for row in progress:
                get_email_status_list(row)

    return data


def check_schools(data, canvas, verbose):
    typer.echo(") Checking enrollments for users with unconfirmed emails...")
    SUB_ACCOUNTS = list()

    for account in ACCOUNTS:
        SUB_ACCOUNTS += find_sub_accounts(canvas, account)

    ROWS = data.itertuples()

    def check_fixable_status(row):
        index, canvas_user_id, email_status = row

        user = canvas.get_user(canvas_user_id)
        user_enrollments = user.get_courses()

        def get_account_id(course):
            try:
                return course.account_id
            except Exception:
                return ""

        account_ids = map(get_account_id, user_enrollments)
        fixable_id = next(
            filter(lambda account: account in SUB_ACCOUNTS, account_ids), None
        )

        if fixable_id:
            if verbose:
                fixable = typer.style("fixable", fg=typer.colors.GREEN)
                typer.echo(f"- Email status for {canvas_user_id} is {fixable}")
            data.at[index, "supported school(s)"] = "Y"
        else:
            if verbose:
                fixable = typer.style("NOT fixable", fg=typer.colors.YELLOW)
                typer.echo(f"- Email status for {canvas_user_id} is {fixable}")
            data.at[index, "supported school(s)"] = "N"

    if verbose:
        for row in ROWS:
            check_fixable_status(row)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for row in progress:
                check_fixable_status(row)

    return data.sort_values(by=["email status"])


def activate_fixable_emails(
    data, canvas, result_path, log_path, include_fixed, verbose
):
    typer.echo(") Activating email accounts for users with unconfirmed emails...")
    NOT_FIXABLE = data[data["supported school(s)"] == "N"]
    FIXABLE = data[
        (data["supported school(s)"] == "Y") & (data["email status"] == "unconfirmed")
    ]
    SUPPORTED_NOT_FOUND = data[
        (data["supported school(s)"] == "Y") & (data["email status"] == "not found")
    ]

    ROWS = FIXABLE.itertuples()

    fixed = 0
    error = 0

    def activate_and_confirm(row):
        index, user_id, email_status, is_supported = row
        user = canvas.get_user(user_id)
        emails = get_user_emails(user)

        for email in emails:
            address = email.address

            if not LOGS.exists():
                Path.mkdir(LOGS)

            with open(log_path, "a") as logger:
                deleted_email_account = {"user": user_id, "email": address}
                logger.write(f"{json.dumps(deleted_email_account)}\n")

            email.delete()
            user.create_communication_channel(
                communication_channel={"address": address, "type": "email"},
                skip_confirmation=True,
            )

        emails = get_user_emails(user)
        email = next(emails, None)
        is_active = get_email_status(user_id, email, False)

        while not is_active:
            next_email = next(emails, None)
            if not next_email:
                if verbose:
                    typer.secho(
                        f"- ERROR: failed to activate email(s) for user {user_id}!",
                        fg=typer.colors.YELLOW,
                    )
                FIXABLE.at[index, "email status"] = "failed to activate"
                error += 1
                break
            is_active = get_email_status(user_id, next_email, False)

        if is_active:
            if verbose:
                typer.echo(f"- Email(s) activated for user: {user_id}")
            FIXABLE.at[index, "email status"] = "auto-activate"
            fixed += 1

    if verbose:
        for row in ROWS:
            activate_and_confirm(row)
    else:
        with typer.progressbar(ROWS, length=(len(FIXABLE.index))) as progress:
            for row in progress:
                activate_and_confirm(row)

    if include_fixed:
        FIXABLE.sort_values(by=["email status"])
        DATA_FRAMES = [FIXABLE, SUPPORTED_NOT_FOUND, NOT_FIXABLE]
    else:
        ERRORS = FIXABLE[FIXABLE["email status"] == "failed to activate"]
        DATA_FRAMES = [ERRORS, SUPPORTED_NOT_FOUND, NOT_FIXABLE]

    RESULT = pandas.concat(DATA_FRAMES)

    typer.echo(f") Saving results to {result_path}...")

    if not RESULTS.exists():
        Path.mkdir(RESULTS)

    RESULT.to_csv(result_path, index=False)

    fixed_count = str(fixed)
    error_count = str(error)
    unsupported_count = str(len(NOT_FIXABLE.index))
    supported_not_found_count = str(len(SUPPORTED_NOT_FOUND.index))

    return fixed_count, error_count, unsupported_count, supported_not_found_count


def style(text):
    return typer.style(text, fg=typer.colors.MAGENTA)


def print_messages(total, fixed, supported_not_found, unsupported, errors):
    typer.echo(f"- Processed {style(total)} accounts.")
    typer.echo(
        f"- Activated {style(fixed)} supported users with unconfirmed email accounts."
    )
    typer.echo(
        f"- Found {style(supported_not_found)} supported users with no email account."
    )
    typer.echo(
        f"- Found {style(unsupported)} unsupported users with missing or unconfirmed"
        " email(s)."
    )
    if errors != "0":
        typer.secho(
            f"- Failed to activate email(s) for {errors} supported users with (an)"
            " unconfirmed email account(s).",
            fg=typer.colors.RED,
        )
    typer.echo("FINISHED")


def email_main(test, include_fixed, verbose):
    report, RESULT_PATH, LOG_PATH = find_users_report()
    report, TOTAL = cleanup_report(report)
    CANVAS = get_canvas(test)
    UNCONFIRMED = find_unconfirmed_emails(report, CANVAS, verbose)
    FIXED = check_schools(UNCONFIRMED, CANVAS, verbose)
    FIXED, ERRORS, UNSUPPORTED, SUPPORTED_NOT_FOUND = activate_fixable_emails(
        FIXED, CANVAS, RESULT_PATH, LOG_PATH, include_fixed, verbose
    )
    print_messages(TOTAL, FIXED, SUPPORTED_NOT_FOUND, UNSUPPORTED, ERRORS)
