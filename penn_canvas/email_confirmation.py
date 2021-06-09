from datetime import datetime
from pathlib import Path

import pandas
import typer

from .canvas_shared import find_sub_accounts, get_canvas, get_command_paths

REPORTS, RESULTS = get_command_paths("email")
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

            return USERS_REPORT.rename(DATED_REPORT), RESULT_PATH


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
                is_active = get_email_status(user_id, email, verbose)
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


def check_school(data, canvas, result_path, verbose):
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

    typer.echo(f") Saving results to {result_path}...")

    if not RESULTS.exists():
        Path.mkdir(RESULTS)

    RESULT = pandas.DataFrame(
        USERS, columns=["canvas user id", "email status", "fixable"]
    )
    return RESULT.sort_values(by=["email status"], inplace=True)
    # RESULT.to_csv(result_path, index=False)
    # fixable_users = len(RESULT[RESULT["fixable"] == "Y"].index)

    # return str(len(RESULT.index)), str(fixable_users)


def activate_fixable_emails(data, canvas, verbose):
    not_found = data[data["fixable"] == "N"]
    not_found = not_found["canvas user id", "email status"]
    fixable = data[data["fixable"] == "Y"]
    fixable = fixable[["canvas user id"]]
    USERS = fixable.itertuples(index=False)
    RESULTS = list()

    for user in fixable:
        print(user)

    for user_id in USERS:
        user = canvas.get_user(user_id)
        emails = get_user_emails(user)

        for email in emails:
            address = email.address
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
                RESULTS.append([user_id, "failed to activate"])
                break
            is_active = get_email_status(user_id, email, False)

        if is_active:
            if verbose:
                typer.echo(f"- Email(s) activated for user: {user_id}")
            RESULTS.append([user_id], "auto-activated")

    # merge RESULTS to dataFrame with not_found


def email_main(test, verbose):
    report, RESULT_PATH = find_users_report()
    report = cleanup_report(report)
    CANVAS = get_canvas(test)
    UNCONFIRMED = find_unconfirmed_emails(report, CANVAS, verbose)
    PROBLEMS, FIXABLE = check_school(UNCONFIRMED, CANVAS, RESULT_PATH, verbose)
    STYLED_PROBLEMS = typer.style(PROBLEMS, fg=typer.colors.MAGENTA)
    STYLED_FIXABLE = typer.style(FIXABLE, fg=typer.colors.MAGENTA)
    typer.echo(
        f"- Found {STYLED_PROBLEMS} users with unconfirmed or missing an email account,"
        f" of which {STYLED_FIXABLE} are manually fixable."
    )
    typer.echo("FINISHED")
