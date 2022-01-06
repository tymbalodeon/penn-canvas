from typer import Argument, Option, Typer

from penn_canvas.course_shopping import course_shopping_main

from .archive import archive_main
from .bulk_enroll import bulk_enroll_main
from .check_enrollment import check_enrollment_main
from .config import print_config, write_config_options
from .count_poll_everywhere import count_poll_everywhere_main
from .count_quizzes import count_quizzes_main
from .count_sites import count_sites_main
from .email import email_main
from .investigate import investigate_main
from .module import module_main
from .nso import nso_main
from .open_canvas_bulk_action import open_canvas_bulk_action_main
from .storage import storage_main
from .tool import tool_main
from .voicethread import voicethread_main

app = Typer(
    help=(
        "Welcome to Penn-Canvas -- working with Penn's Canvas instances has never been"
        " easier!"
    )
)


@app.command()
def voicethread():
    voicethread_main()


@app.command()
def course_shopping(
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
    disable: bool = Option(
        False,
        "--disable",
        help="Disable course shopping instead of enable",
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
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
):
    course_shopping_main(test, disable, force, verbose, new)


@app.command()
def archive(
    course: int = Argument(
        ..., help="The course whose discussions you want to archive."
    ),
    instance: str = Argument(
        "prod",
        help="The Canvas instance to use.",
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
    timestamp: bool = Option(
        False,
        "--timestamp",
        help="Include the timestamp in the output.",
    ),
    content: bool = Option(
        False,
        "--content",
        help="Export course content in the archive output.",
    ),
    announcements: bool = Option(
        False,
        "--announcements",
        help="Export course announcements in the archive output.",
    ),
    modules: bool = Option(
        False,
        "--modules",
        help="Export course modules in the archive output.",
    ),
    pages: bool = Option(
        False,
        "--pages",
        help="Export course pages in the archive output.",
    ),
    syllabus: bool = Option(
        False,
        "--syllabus",
        help="Export course syllabus in the archive output.",
    ),
    assignments: bool = Option(
        False,
        "--assignments",
        help="Inlcude assignments in the archive output.",
    ),
    discussions: bool = Option(
        False,
        "--discussions",
        help="Inlcude discussions in the archive output.",
    ),
    grades: bool = Option(
        False,
        "--grades",
        help="Inlcude grades in the archive output.",
    ),
    quizzes: bool = Option(
        False,
        "--quizzes",
        help="Inlcude quizzes in the archive output.",
    ),
):
    """
    Archives a Canvas course's discussions and quiz participation.

    INPUT: Canvas course id whose discussions (and optionally quiz
    participation) you want to archive

    OUTPUT: Folder with the course name containing csv files for each
    discussion, listing the user, email, (OPTIONAL: timestamp), and post; as
    well as a list of users who submitted for each of the course's quizzes.
    """
    archive_main(
        course,
        instance,
        verbose,
        timestamp,
        content,
        announcements,
        modules,
        pages,
        syllabus,
        assignments,
        discussions,
        grades,
        quizzes,
    )


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
    Enrolls a given user into all courses for the given school and terms.

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
def check_enrollment(
    course: int = Argument(
        ...,
        help="The Canvas course id of the course whose enrollments you wish to check.",
    ),
    year: int = Argument(
        ...,
        help=(
            "The year of the start date for checking enrollments, in the format: YYYY."
        ),
    ),
    month: int = Argument(
        ...,
        help=(
            "The month of the start date for checking enrollments, in the format: M or"
            " MM (Do not use leading zeros)."
        ),
    ),
    day: int = Argument(
        ...,
        help=(
            "The day of the start date for checking enrollments, in the format: D or DD"
            " (Do not use leading zeros)."
        ),
    ),
    instance: str = Option(
        "prod",
        "--instance",
        help=(
            'The Canvas instnace to check. Can be one of the following: "prod", "test",'
            ' "open", "open_test".'
        ),
    ),
):
    """
    Check enrollment.
    """
    check_enrollment_main(course, year, month, day, instance)


@app.command()
def config(
    update: bool = Option(
        False,
        "--update",
        help="Update the config instead of displaying",
    ),
    show_secrets: bool = Option(
        False,
        "--show-secrets",
        help="Display sensitive values on screen",
    ),
):
    """
    Automatically generates a config file for Penn-Canvas.

    INPUT: Canvas Access Token(s) for

    - PRODUCTION: `https://canvas.upenn.edu/`

    - TEST: `https://upenn.test.instructure.com/`

    - OPEN: `https://upenn-catalog.instructure.com/`

    - OPEN TEST: `https://upenn-catalog.test.instructure.com/`

    OUTPUT: config file located at $HOME/.config/penn-canvas

    To generate these tokens, login to the appropriate Canvas instance using one
    of the urls above. Go to 'Account > Settings' and click 'New Access Token'
    under the 'Approved Integrations' heading. Enter a description in the
    'Purpose' field and click 'Generate Token'. Paste this token into the
    terminal when prompted by the `configure` command. You do not need to
    include all three; for each one you will be asked whether you want to
    include it in your config.
    """
    write_config_options() if update else print_config(show_secrets)


@app.command()
def count_poll_everywhere(
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/)"
            " instead of production (https://canvas.upenn.edu/)."
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
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """
    Generates a report of poll everywhere usage for the courses provided as input.
    """
    count_poll_everywhere_main(test, force, verbose)


@app.command()
def count_quizzes(
    new_quizzes: bool = Option(
        False, "--new-quizzes", help="Count New Quizzes instead of Classic Quizzes."
    ),
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/)"
            " instead of production (https://canvas.upenn.edu/)."
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
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """
    Generates a report of quiz usage for the courses provided as input.
    """
    count_quizzes_main(new_quizzes, test, force, verbose)


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
def investigate():
    """Investigate student assignments"""
    investigate_main()


@app.command()
def module(
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)"
        ),
    ),
    course_id: int = Argument(
        ...,
        help="The Canvas course id of the course whose modules you want to re-lock.",
    ),
):
    """Re-lock a courses modules."""
    module_main(test, course_id)


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
def open_canvas_bulk_action(
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
    test: bool = Option(
        False,
        "--test",
        help="Use the Open Canvas test instance instead of production.",
    ),
):
    open_canvas_bulk_action_main(verbose, force, test)


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
