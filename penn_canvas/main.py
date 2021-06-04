import typer

from .canvas_shared import make_config
from .course_storage_quota import storage_main
from .email_confirmation import email_main

# import email_confirmation
# import module_progression_lock
# import piazza_report
# import quiz_students_check
# import reserve
# import student_integrity_check
# import zoom_check

MAIN_HELP = """
    Welcome to the Penn-Canvas -- working with Canvas has never been easier!
"""
app = typer.Typer(help=MAIN_HELP)


@app.command()
def configure():
    """
    Automatically generate a config file for Penn-Canvas
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
        help="Use the Canvas test instance (https://upenn.test.instructure.com/) instead of production",
    ),
    verbose: bool = typer.Option(False, "--verbose"),
):
    """
    Increases the storage quota for each course that currently uses 79% or more
    of its current storage allotment.

    Requires a Canvas course storage report as input. To download, login to
    `https://canvas.upenn.edu/` (admin priveledges are required) and click
    'Admin > Upenn > Settings > Reports', then click 'Configure...' to the right
    of 'Course storage.' When notified that the report has finished generating,
    download the file (click the down arrow icon) and place it in:
    $HOME/canvas-cli/storage/reports/. Once the file has been added to the
    directory, run this command.

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
        help="Use the Canvas test instance (https://upenn.test.instructure.com/) instead of production",
    ),
    # verbose: bool = typer.Option(False, "--verbose"),
):
    """
    Email confirmation
    """
    email_main(test)


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
