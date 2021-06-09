import json
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .canvas_shared import find_sub_accounts, get_canvas, get_command_paths

REPORTS, RESULTS, LOGS = get_command_paths("email")
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
            typer.echo(
                "\tA Canvas Users Provisioning report was not found.\n\tPlease add a"
                " Canvas Users Provisioning report to this directory and then run this"
                " script again.\n\t(If you need instructions for generating a Canvas"
                " Provisioning report, run this command with the '--help' flag.)"
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

    return data


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
    USERS = data.itertuples(index=False)
    UNCONFIRMED = list()

    def get_email_status_list(user):
        user_id = user.canvas_user_id
        user = canvas.get_user(user_id)
        emails = get_user_emails(user)
        email = next(emails, None)

        if email:
            is_active = get_email_status(user_id, email, verbose)

            while not is_active:
                next_email = next(emails, None)
                if not next_email:
                    if verbose:
                        status = typer.style("unconfirmed", fg=typer.colors.YELLOW)
                        typer.echo(f"- Email status is {status} for user: {user_id}")
                    UNCONFIRMED.append([user_id, "unconfirmed"])
                    break
                is_active = get_email_status(user_id, next_email, verbose)
        else:
            if verbose:
                error = typer.style("No email found for user:", fg=typer.colors.YELLOW)
                typer.echo(f"- {error} {user_id}")
            UNCONFIRMED.append([user_id, "not found"])

    if verbose:
        for user in USERS:
            get_email_status_list(user)
    else:
        with typer.progressbar(USERS, length=len(data.index)) as progress:
            for user in progress:
                get_email_status_list(user)

    return pandas.DataFrame(UNCONFIRMED, columns=["canvas user id", "email status"])


def check_school(data, canvas, verbose):
    typer.echo(") Checking enrollments for users with unconfirmed emails...")
    SUB_ACCOUNTS = list()
    USERS = list()

    for account in ACCOUNTS:
        SUB_ACCOUNTS += find_sub_accounts(canvas, account)

    ROWS = data.itertuples(index=False)

    def check_fixable_status(row):
        canvas_user_id, email_status = row

        if email_status == "not found":
            USERS.append([canvas_user_id, email_status, "N"])
            return

        user = canvas.get_user(canvas_user_id)
        user_enrollments = user.get_courses()
        account_ids = map(lambda account: account.account_id, user_enrollments)
        fixable_id = next(
            filter(lambda account: account in SUB_ACCOUNTS, account_ids), None
        )

        if fixable_id:
            if verbose:
                fixable = typer.style("fixable", fg=typer.colors.GREEN)
                typer.echo(f"- Email status for {canvas_user_id} is {fixable}")
            USERS.append([canvas_user_id, email_status, "Y"])
        else:
            if verbose:
                fixable = typer.style("NOT fixable", fg=typer.colors.YELLOW)
                typer.echo(f"- Email status for {canvas_user_id} is {fixable}")
            USERS.append([canvas_user_id, email_status, "N"])

    if verbose:
        for row in ROWS:
            check_fixable_status(row)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for row in progress:
                check_fixable_status(row)

    RESULT = pandas.DataFrame(
        USERS, columns=["canvas user id", "email status", "fixable"]
    )
    return RESULT.sort_values(by=["email status"], inplace=True)


def activate_fixable_emails(data, canvas, result_path, log_path, verbose):
    typer.echo(") Activating email accounts for users with unconfirmed emails...")
    not_fixable = data[data["fixable"] == "N"]
    not_fixable = not_fixable["canvas user id", "email status"]

    fixable = data[data["fixable"] == "Y"]
    fixable = fixable[["canvas user id"]]

    USERS = fixable.itertuples(index=False)
    FIXED = list()
    ERRORS = list()

    def activate_and_confirm(user_id):
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

        new_emails = get_user_emails(user)
        email = next(new_emails, None)
        is_active = get_email_status(user_id, email, False)

        while not is_active:
            next_email = next(emails, None)
            if not next_email:
                if verbose:
                    typer.secho(
                        f"- ERROR: failed to activate email(s) for user {user_id}!",
                        fg=typer.colors.YELLOW,
                    )
                ERRORS.append([user_id, "failed to activate"])
                break
            is_active = get_email_status(user_id, next_email, False)

        if is_active:
            if verbose:
                typer.echo(f"- Email(s) activated for user: {user_id}")
            FIXED.append([user_id], "auto-activated")

    if verbose:
        for user_id in USERS:
            activate_and_confirm(user_id)
    else:
        with typer.progressbar(USERS, length=(len(fixable.index))) as progress:
            for user_id in progress:
                activate_and_confirm(user_id)

    fixed_count = str(len(FIXED))
    error_count = str(len(ERRORS))
    FIXED += ERRORS
    UPDATED = pandas.DataFrame(FIXED, columns=["canvas user id", "email status"])
    RESULT = pandas.concat([UPDATED, not_fixable])

    typer.echo(f") Saving results to {result_path}...")

    if not RESULTS.exists():
        Path.mkdir(RESULTS)

    RESULT.to_csv(result_path, index=False)

    return fixed_count, error_count


def email_main(test, verbose):
    report, RESULT_PATH, LOG_PATH = find_users_report()
    report = cleanup_report(report)
    CANVAS = get_canvas(test)
    UNCONFIRMED = find_unconfirmed_emails(report, CANVAS, verbose)
    FIXED = check_school(UNCONFIRMED, CANVAS, RESULT_PATH, verbose)
    FIXED, ERRORS = activate_fixable_emails(
        FIXED, CANVAS, RESULT_PATH, LOG_PATH, verbose
    )
    STYLED_FIXED = typer.style(FIXED, fg=typer.colors.MAGENTA)
    typer.echo(f"- Activated {STYLED_FIXED} users with unconfirmed email accounts.")
    typer.secho(
        f"- Failed to activate email(s) for {ERRORS} users with (an) unconfirmed email"
        " account(s).",
        fg=typer.colors.RED,
    )
    typer.echo("FINISHED")
