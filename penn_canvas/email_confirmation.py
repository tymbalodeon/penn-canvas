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


def find_unconfirmed_emails(data, canvas, verbose):
    typer.echo(") Finding unconfirmed emails...")
    USERS = data.itertuples(index=False)
    UNCONFIRMED = list()

    def check_email_status(user):
        user_id = user.canvas_user_id
        user = canvas.get_user(user_id)
        communication_channels = user.get_communication_channels()

        try:
            email_status = communication_channels[0].workflow_state

            if email_status == "unconfirmed":
                if verbose:
                    status = typer.style(f"{email_status}", fg=typer.colors.YELLOW)
                    typer.echo(f"- Email status is {status} for user: {user_id}")
                UNCONFIRMED.append([user_id, email_status])
            elif email_status == "active" and verbose:
                status = typer.style(f"{email_status}", fg=typer.colors.GREEN)
                typer.echo(f"- Email status is {status} for user: {user_id}")
        except IndexError:
            if verbose:
                error = typer.style("No email found for user:", fg=typer.colors.YELLOW)
                typer.echo(f"- {error} {user_id}")
            UNCONFIRMED.append([user_id, "not found"])

    if verbose:
        for user in USERS:
            check_email_status(user)
    else:
        with typer.progressbar(USERS, length=len(data.index)) as progress:
            for user in progress:
                check_email_status(user)

    return pandas.DataFrame(UNCONFIRMED, columns=["canvas user id", "email status"])


def check_school(data, canvas, result_path, verbose):
    typer.echo(") Checking enrollments for users with unconfirmed emails...")
    SUB_ACCOUNTS = list()
    USERS = list()
    fixable_users = 0

    for account in ACCOUNTS:
        SUB_ACCOUNTS += find_sub_accounts(canvas, account)

    ROWS = data.itertuples(index=False)

    def check_fixable_status(row):
        canvas_user_id, email_status = row
        user = canvas.get_user(canvas_user_id)
        user_enrollments = user.get_courses()
        account_ids = map(lambda x: x.account_id, user_enrollments)
        fixable_id = next(filter(lambda x: x in SUB_ACCOUNTS, account_ids), None)

        if fixable_id:
            if verbose:
                fixable = typer.style("fixable", fg=typer.colors.GREEN)
                typer.echo(f"- Email status for {canvas_user_id} is {fixable}")
            USERS.append([canvas_user_id, email_status, "Y"])
            fixable_users += 1
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
    RESULT.to_csv(result_path, index=False)
    return str(len(RESULT.index)), str(fixable_users)


def email_main(test, verbose):
    report, RESULT_PATH = find_users_report()
    report = cleanup_report(report)
    CANVAS = get_canvas(test)
    UNCONFIRMED = find_unconfirmed_emails(report, CANVAS, verbose)
    PROBLEMS, FIXABLE = check_school(UNCONFIRMED, CANVAS, RESULT_PATH, verbose)
    STYLED_PROBLEMS = typer.style(PROBLEMS, fg=typer.colors.MAGENTA)
    STYLED_FIXABLE = typer.style(FIXABLE, fg=typer.colors.MAGENTA)
    typer.echo(
        f"- Found {STYLED_PROBLEMS} users with unconfirmed or missing an email account, of which {STYLED_FIXABLE} are manually fixable."
    )
    typer.echo("FINISHED")
