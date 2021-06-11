import typer

from .helpers import make_config
from .course_storage_quota import storage_main
from .email_confirmation import email_main

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
def configure():
    """
    Automatically generate a config file for Penn-Canvas.
    """
    make_config()


@app.command()
def shopping():
    """
    Course shopping
    """
    typer.echo("test")


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
    verbose: bool = typer.Option(False, "--verbose"),
):
    """
    Increases the storage quota for each course that currently uses 79% or more
    of its current storage allotment.

    Requires a Canvas Course Storage report as input. To download, login to
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
    verbose: bool = typer.Option(False, "--verbose"),
):
    """
    Checks the email status of users and activates any unconfirmed email
    addresses for users with at least one enrollment in a "supported" school.
    Outputs a list of users who either have no email accounts, or who have
    unconfirmed accounts but have no enrollments in a "supported" school.

    "Supported" schools are all schools EXCEPT:

        Wharton, Perelman School of Medicine ("PSOM")

    Requires a Canvas Provisioning Users CSV report as input. To download,
    login to `https://canvas.upenn.edu/` (admin priveledges are required) and
    click 'Admin > Upenn > Settings > Reports', then click 'Configure...' to the
    right of 'Provisioning.' Select the desired term, check "Users CSV" and
    click 'Run Report.' When notified that the report has finished generating,
    download the file (click the down arrow icon) and place it in:
    $HOME/penn-canvas/email/reports/. Once the file has been added to the
    directory, run this command.
    """
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
