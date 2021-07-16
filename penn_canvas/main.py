import typer

from .course_storage_quota import storage_main
from .email_confirmation import email_main
from .group_enrollments import group_enrollments_main
from .helpers import display_config, make_config

# import email_confirmation
# import module_progression_lock
# import piazza_report
# import quiz_students_check
# import reserve
# import student_integrity_check
# import zoom_check

app = typer.Typer(
    help="""Welcome to the Penn-Canvas -- working with Canvas has never been easier!"""
)


@app.command()
def config(
    view: bool = typer.Option(
        False,
        "--view",
        help=(
            "Display your config's values instead of creating or updating your config."
        ),
    )
):
    """
    Automatically generates a config file for Penn-Canvas.

    INPUT: Canvas Access Token(s) for

    - PRODUCTION: `https://canvas.upenn.edu/`

    - DEVELOPMENT: `https://upenn.test.instructure.com/`

    - OPEN: `https://upenn-catalog.instructure.com/`

    OUTPUT: config file located at $HOME/.config/penn-canvas

    To generate these tokens, login to the appropriate Canvas instance using one
    of the urls above. Go to 'Account > Settings' and click 'New Access Token'
    under the 'Approved Integrations' heading. Enter a description in the
    'Purpose' field and click 'Generate Token'. Paste this token into the
    terminal when prompted by the `configure` command. You do not need to
    include all three; for each one you will be asked whether you want to
    include it in your config.
    """

    if view:
        display_config()
    else:
        make_config()


@app.command()
def shopping():
    """
    Course shopping
    """

    typer.echo("test")


@app.command()
def group_enrollments(
    test: bool = typer.Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)"
        ),
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
):
    """
    Group enrollments
    """

    group_enrollments_main(test, verbose, force)


@app.command()
def storage(
    test: bool = typer.Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)"
        ),
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """
    Increases the storage quota for each course that currently uses 79% or more
    of its current storage allotment.

    INPUT: Canvas Course Storage report

    OUTPUT: A csv file listing courses whose storage was increased

    To download a Canvas Course Storage report, login to
    `https://canvas.upenn.edu/` (admin priveledges are required) and click
    'Admin > Upenn > Settings > Reports', then click 'Configure...' to the right
    of 'Course storage.' Select the desired term and click 'Run Report.' When
    notified that the report has finished generating, download the file (click
    the down arrow icon) and place it in: $HOME/penn-canvas/storage/reports/.
    Once the file has been added to the directory, run this command.

    NOTE: This command must be run on the same day that the storage report was
    generated (as indicated in the file name). A file whose name contains a
    previous date will not be accepted.
    """

    storage_main(test, verbose)


@app.command()
def email(
    test: bool = typer.Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)"
        ),
    ),
    include_fixed: bool = typer.Option(
        False,
        "--include-fixed",
        help=(
            "Include in the output file the list of users whose email accounts were"
            " automatically activated by the script"
        ),
    ),
    verbose: bool = typer.Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """
    Checks the email status of users and activates any unconfirmed email
    addresses for users with at least one enrollment in a "supported" school.

    INPUT: Canvas Provisioning report (Users)

    OUTPUT: A csv file listing users who either have no email accounts, or who
    have unconfirmed accounts but have no enrollments in a "supported" school
    (and optionally listing users whose accounts were successfully activated)

    "Supported" schools are all schools EXCEPT:

        Wharton, Perelman School of Medicine

    To download a Canvas Provisioning report for Users, login to
    `https://canvas.upenn.edu/` (admin priveledges are required) and click
    'Admin > Upenn > Settings > Reports', then click 'Configure...' to the right
    of 'Provisioning.' Select the desired term, check "Users CSV" and click 'Run
    Report.' When notified that the report has finished generating, download the
    file (click the down arrow icon) and place it in:
    $HOME/penn-canvas/email/reports/. Once the file has been added to the
    directory, run this command."""

    email_main(test, include_fixed, verbose)


@app.command()
def module():
    """
    Module progression lock
    """
    typer.echo("module")


@app.command()
def piazza():
    """
    Piazza report
    """
    typer.echo("piazza")


@app.command()
def quiz():
    """
    Quiz students check
    """
    typer.echo("quiz")


@app.command()
def reserve():
    """
    Reserve commands (enable and report)
    """
    typer.echo("reserve")


@app.command()
def integrity():
    """
    Student integrity check
    """
    typer.echo("integrity")


@app.command()
def zoom():
    """
    Zoom check
    """
    typer.echo("zoom")
