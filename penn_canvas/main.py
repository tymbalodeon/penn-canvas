from typer import Argument, Option, Typer

from .archive import archive_main
from .bulk_enroll import bulk_enroll_main
from .count_sites import count_sites_main
from .email import email_main
from .helpers import display_config, make_config
from .nso import nso_main
from .open_canvas_enroll import open_canvas_enroll_main
from .storage import storage_main
from .tool import tool_main

app = Typer(
    help=(
        "Welcome to Penn-Canvas -- working with Penn's Canvas instances has never been"
        " easier!"
    )
)


@app.command()
def archive(
    course: int = Argument(
        ..., help="The course whose discussions you want to archive."
    ),
    instance: str = Argument(
        "open",
        help="The Canvas instance to use.",
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
):
    """
    Archives a Canvas course's discussions.

    INPUT: Canvas course id whose discussions you want to archive

    OUTPUT: Folder with the course name containing csv files for each
    discussion, listing the user, timestamp, and post
    """

    archive_main(course, instance, verbose, force)


@app.command()
def bulk_enroll(
    user: int = Option(
        5966278, "--user", help="The Canvas user id of the user to be bulk enrolled."
    ),
    sub_account: int = Option(
        99241,
        "--sub-account",
        help="The Canvas account id of the school to pull courses from.",
    ),
    terms: list[int] = Option(
        [
            5773,
            5799,
            5818,
            5833,
            5901,
            5910,
            5956,
            5988,
            6008,
            6055,
            6086,
            6112,
            6139,
            6269,
            6291,
            6304,
            6321,
            5688,
            5821,
            5911,
            6063,
            6120,
            6303,
            4373,
            2244,
        ],
        "--terms",
        help="A list of Canvas enrollment term ids to pull courses from.",
    ),
    input_file: bool = Option(
        True,
        "--no-input-file",
        help="Use a csv file to input terms instead of a command-line option.",
    ),
    dry_run: bool = Option(
        False,
        "--dry-run",
        help=(
            "Ouput a list of courses found for the given school and terms without"
            " enrolling the user."
        ),
    ),
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
    check_errors: bool = Option(
        False,
        "--check-errors",
        help=(
            "Attempt to enroll user in courses that previously hit an error (skips"
            " errors by default)."
        ),
    ),
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help="Clear the list of courses already processed for a given user/school.",
    ),
):
    """
    Enrolls a given user into all courses found for the given school and terms.

    """
    bulk_enroll_main(
        user,
        sub_account,
        terms,
        input_file,
        dry_run,
        test,
        check_errors,
        clear_processed,
    )


@app.command()
def config(
    view: bool = Option(
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
def count_sites(
    year_and_term: str = Argument(
        ...,
        help=(
            "The term to limit the count to, in the form of year (YYYY) plus term code"
            " (A for spring, B for summer, C for fall) - e.g. '2021C'"
        ),
    ),
    separate: bool = Option(
        False,
        "--separate-graduate",
        help="Separate the count into undergraduate and graduate courses.",
    ),
    graduate_course_minimum_number: int = Argument(
        500, help="The course number at which or above designates a graduate course."
    ),
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
):
    """
    Counts the number of unique course numbers that have a Canvas site.
    """

    count_sites_main(year_and_term, separate, graduate_course_minimum_number, test)


@app.command()
def email(
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    new: bool = Option(
        False,
        "--new",
        help=(
            "Process only newly added users, skipping previous users that encountered"
            " errors."
        ),
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help="Clear the list of users already processed for the current year.",
    ),
    no_data_warehouse: bool = Option(
        False,
        "--no-data-warehouse",
        help=(
            "Don't check the Data Warehouse (use when access to the Data Warehouse is"
            " unavailable.)"
        ),
    ),
):
    """
    Checks the email status of users and activates any unconfirmed email
    addresses for users with at least one enrollment in a "supported" school.

    INPUT: Canvas Provisioning (Users) report

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
    directory, run this command.

    NOTE: Input filename must include the current date in order to be accepted.
    """

    email_main(test, verbose, new, force, clear_processed, no_data_warehouse)


@app.command()
def nso(
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)"
        ),
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help="Clear the list of users already processed for the current year.",
    ),
):
    """
    ('NSO' stands for 'New Student Orientation'.) Enrolls incoming freshmen into
    Canvas Groups as part of the 'Thrive at Penn' site.

    INPUT: An xlsx file (assumes graduation year is in the file name) with the
    columns [Canvas Course ID | Group Set Name | Group Name | User (Pennkey)]

    OUPUT: A csv file listing students who were not successfully added to a
    Group

    NOTE: This command assumes a graduation year of 4 years from the current
    year when the command is run. A file whose name contains any other year will
    not be accepted.
    """

    nso_main(test, verbose, force, clear_processed)


@app.command()
def open_canvas_enroll(
    remove: bool = Option(
        False, "--remove", help="Remove user accounts instead of create them."
    ),
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn-catalog.test.instructure.com)"
            " instead of production (https://upenn-catalog.instructure.com)."
        ),
    ),
):
    open_canvas_enroll_main(remove, test)


@app.command()
def storage(
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
    increase: int = Option(
        1000, "--increase", help="The amount in MB to increase a course's storage."
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

    NOTE: Input filename must include the current date in order to be accepted.
    """

    storage_main(test, verbose, force, increase)


@app.command()
def tool(
    tool: str = Argument(
        ...,
        help=(
            "The Canvas external tool you wish to work with. Must match the tool's"
            " Canvas tab's label, or id if using --id."
        ),
    ),
    use_id: bool = Option(
        False,
        "--id",
        help="Locate the specified tool using the tool's tab's id rather than label.",
    ),
    enable: bool = Option(
        False,
        "--enable",
        help="Enable the specified tool rather than generate a usage report.",
    ),
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    new: bool = Option(
        False,
        "--new",
        help=(
            "Process only newly added courses, skipping previous courses that"
            " encountered errors."
        ),
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help=(
            "Clear the list of courses already processed for the term(s). Only runs if"
            " '--enable' is also used."
        ),
    ),
):
    """
    Returns a list of courses with TOOL enabled or enables TOOL for a list of
    courses if using '--enable'.

    INPUT: Canvas Provisioning (Courses) report(s)

    OUTPUT: A csv file listing courses with TOOL enabled

    To download a Canvas Provisioning report for Courses, login to
    `https://canvas.upenn.edu/` (admin priveledges are required) and click
    'Admin > Upenn > Settings > Reports', then click 'Configure...' to the right
    of 'Provisioning.' Select the desired term, check "Courses CSV" and click 'Run
    Report.' When notified that the report has finished generating, download the
    file (click the down arrow icon) and place it in:
    $HOME/penn-canvas/tool/reports/. Once the file has been added to the
    directory, run this command.

    NOTE: This command accepts multiple input files to allow for checking
    multiple terms at once. Any file whose name contains the current date will
    be included in the task. The results will always be combined into a single
    output file.
    """

    tool_main(tool, use_id, enable, test, verbose, new, force, clear_processed)
