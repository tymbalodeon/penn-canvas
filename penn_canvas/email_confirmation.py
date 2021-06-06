from pathlib import Path

import pandas
import typer

from .canvas_shared import find_sub_accounts, get_canvas

EMAIL = Path.home() / "penn-canvas/email"
REPORTS = EMAIL / "reports"
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
        USERS_REPORT = REPORTS / "users.csv"

        if not USERS_REPORT.exists():
            typer.echo(
                "\tA Canvas Users Provisioning report  was not found.\n\tPlease add a"
                " Canvas Users Provisioning report to this directory and then run this"
                " script again.\n\t(If you need instructions for generating a Canvas"
                " Provisioning report, run this command with the '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            return USERS_REPORT


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

    for user in USERS:
        user_id = user.canvas_user_id
        user = canvas.get_user(user_id)
        communication_channels = user.get_communication_channels()

        try:
            email_status = communication_channels[0].workflow_state
        except:
            if verbose:
                error = typer.style("Error occured for user:", fg=typer.colors.YELLOW)
                typer.echo(f"- {error} {user_id}")
            UNCONFIRMED.append([user_id, "ERROR"])

        if email_status == "unconfirmed":
            if verbose:
                status = typer.style(f"{email_status}", fg=typer.colors.YELLOW)
                typer.echo(f"- Email status is {status} for {user_id}")
            UNCONFIRMED.append([user_id, email_status])
        elif verbose:
            status = typer.style(f"{email_status}", fg=typer.colors.GREEN)
            typer.echo(f"- Email status is {status} for user: {user_id}")

    return pandas.DataFrame(UNCONFIRMED, columns=["canvas user id", "email status"])


def check_school(data, canvas, verbose):
    typer.echo(") Checking enrollments for users with unconfirmed emails...")
    SUB_ACCOUNTS = list()
    USERS = list()

    for account in ACCOUNTS:
        SUB_ACCOUNTS += find_sub_accounts(canvas, account)

    ROWS = data.itertuples(index=False)

    for row in ROWS:
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
        else:
            if verbose:
                fixable = typer.style("NOT fixable", fg=typer.colors.YELLOW)
                typer.echo(f"- Email status for {canvas_user_id} is {fixable}")
            USERS.append([canvas_user_id, email_status, "N"])

    return pandas.DataFrame(
        USERS, columns=["canvas user id", "email status", "fixable"]
    )


def email_main(test, verbose):
    report = find_users_report()
    report = cleanup_report(report)
    CANVAS = get_canvas(test)
    UNCONFIRMED = find_unconfirmed_emails(report, CANVAS, verbose)
    check_school(UNCONFIRMED, CANVAS, verbose)
    typer.echo("FINISHED")
