from typing import Optional

from typer import Argument, Option, Typer

from penn_canvas.api import Instance
from penn_canvas.roles import roles_main

from .archive.archive import archive_main
from .browser import browser_main
from .bulk_enroll import bulk_enroll_main
from .check_enrollment import check_enrollment_main
from .config import print_config, write_config_options
from .constants import PENN_CANVAS_MAIN_ACCOUNT_ID
from .count_poll_everywhere import count_poll_everywhere_main
from .count_quizzes import count_quizzes_main
from .count_sites import count_sites_main
from .course_shopping import course_shopping_main
from .email import email_main
from .find_users_by_email import find_users_by_email_main
from .helpers import CURRENT_YEAR_AND_TERM
from .integrity import integrity_main
from .investigate import investigate_main
from .module import module_main
from .new_student_orientation import new_student_orientation_main
from .open_canvas_bulk_action import open_canvas_bulk_action_main
from .report import report_main
from .storage import storage_main
from .tool import tool_main
from .update_term import update_term_main
from .usage_count import usage_count_main

app = Typer(help="CLI for managing Penn's Canvas instances")


@app.command()
def archive(
    course_ids: Optional[list[int]] = Option(None, "--course", help="Canvas course id"),
    terms: list[str] = Option([CURRENT_YEAR_AND_TERM], "--term", help="Term name"),
    instance_name: str = Option(
        Instance.PRODUCTION.value, "--instance", help="Canvas instance name"
    ),
    use_timestamp: bool = Option(
        False, "--timestamp", help="Include/exclude the timestamp in the output"
    ),
    content: Optional[bool] = Option(
        None, "--content/--no-content", help="Include/exclude course content"
    ),
    announcements: Optional[bool] = Option(
        None,
        "--announcements/--no-announcements",
        help="Include/exclude course announcements",
    ),
    groups: Optional[bool] = Option(
        None, "--groups/--no-groups", help="Include/exclude course groups"
    ),
    modules: Optional[bool] = Option(
        None, "--modules/--no-modeules", help="Include/exclude course modules"
    ),
    pages: Optional[bool] = Option(
        None, "--pages/--no-pages", help="Include/exclude course pages"
    ),
    syllabus: Optional[bool] = Option(
        None, "--syllabus/--no-syllabus", help="Include/exclude course syllabus"
    ),
    assignments: Optional[bool] = Option(
        None,
        "--assignments/--no-assignments",
        help="Include/exclude course assignments",
    ),
    discussions: Optional[bool] = Option(
        None,
        "--discussions/--no-discussions",
        help="Include/exclude course discussions",
    ),
    grades: Optional[bool] = Option(
        None, "--grades/--no-grades", help="Include/exclude course grades"
    ),
    rubrics: Optional[bool] = Option(
        None, "--rubrics/--no-rubrics", help="Include/exclude course rubrics"
    ),
    quizzes: Optional[bool] = Option(
        None, "--quizzes/--no-quizzes", help="Include/exclude course quizzes"
    ),
    force_report: bool = Option(
        False,
        "--force-report",
        help="Ignore cache and force a new report to be generated",
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print verbose output to the console"
    ),
):
    """
    Archive Canvas courses


    Options with "include" and "exclude" flags will all be included if none of
    the flags are specified.

    """
    archive_main(
        course_ids,
        terms,
        instance_name,
        use_timestamp,
        content,
        announcements,
        modules,
        pages,
        syllabus,
        assignments,
        groups,
        discussions,
        grades,
        rubrics,
        quizzes,
        force_report,
        verbose,
    )


@app.command()
def browser(
    course_ids: Optional[list[int]] = Option(None, "--course", help="Canvas course id"),
    instance_name: str = Option(
        Instance.OPEN.value, "--instance", help="Canvas instance name"
    ),
    force: bool = Option(False, "--force", help="Overwrite existing results"),
    verbose: bool = Option(
        False, "--verbose", help="Print verbose output to the console"
    ),
):
    """
    Report user browser data for Canvas courses
    """
    browser_main(course_ids, instance_name, force, verbose)


@app.command()
def bulk_enroll(
    user: int = Option(5966278, "--user", help="Canvas user id"),
    sub_account: int = Option(99241, "--sub-account", help="Canvas account id"),
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
        help="Canvas enrollment term id",
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
    Enroll user into multiple courses

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
    """Enable or disable Course Shopping 'Institution' level visibility for courses."""
    course_shopping_main(test, disable, force, verbose, new)


@app.command()
def email(
    instance_name: str = Option(
        Instance.PRODUCTION.value,
        "--instance",
        help="The Canvas instance to use.",
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
    force_report: bool = Option(
        False,
        "--force-report",
        help="Force a new report to be generated rather than use a cahced one.",
    ),
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help="Clear the list of users already processed for the current year.",
    ),
    use_data_warehouse: bool = Option(
        True,
        " /--no-data-warehouse",
        help="Whether or not to check the Data Warehouse",
    ),
    prompt: bool = Option(
        True, " /--no-prompt", help="Print out detailed information as the task runs."
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """
    Checks the email status of users and activates any unconfirmed email
    addresses for users with at least one enrollment in a "supported" school.

    "Supported" schools are all schools EXCEPT:

        Wharton, Perelman School of Medicine
    """
    email_main(
        instance_name,
        new,
        force,
        force_report,
        clear_processed,
        use_data_warehouse,
        prompt,
        verbose,
    )


@app.command()
def find_users_by_email(
    emails_path: str = Argument(
        "",
        help="The path to the emails csv.",
    )
):
    """
    Find users in Canvas when all you have is an email.
    """
    find_users_by_email_main(emails_path)


@app.command()
def integrity(
    course: int = Option(..., "--course", help="The course id to check"),
    users: str = Option(
        ...,
        "--users",
        help="The user ids to check",
    ),
    quizzes: str = Option(
        ...,
        "--quizzes",
        help="The quiz ids to check",
    ),
    test: bool = Option(
        False,
        "--test",
        help=(
            "Use the Canvas test instance (https://upenn.test.instructure.com/) instead"
            " of production (https://canvas.upenn.edu/)."
        ),
    ),
    skip_page_views: bool = Option(
        False,
        "--skip-page-views",
        help="Skip pulling page view data, which is time consuming.",
    ),
):
    """
    Check page views for students taking quizzes.
    """
    integrity_main(course, users, quizzes, test, skip_page_views)


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
def new_student_orientation(
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
    Enrolls incoming freshmen into
    Canvas Groups as part of the 'Thrive at Penn' site.

    INPUT: An xlsx file (assumes graduation year is in the file name) with the
    columns [Canvas Course ID | Group Set Name | Group Name | User (Pennkey)]

    OUPUT: A csv file listing students who were not successfully added to a
    Group

    NOTE: This command assumes a graduation year of 4 years from the current
    year when the command is run. A file whose name contains any other year will
    not be accepted.
    """
    new_student_orientation_main(test, verbose, force, clear_processed)


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
    """Run any Open Canvas Bulk Action input files currently in the Input folder"""
    open_canvas_bulk_action_main(verbose, force, test)


@app.command()
def report(
    report_type: str = Option(
        "provisioning",
        "--report-type",
        help="The report type to get or create",
    ),
    term: str = Option(
        CURRENT_YEAR_AND_TERM,
        "--term-name",
        help="The display name of the term for the report",
    ),
    force: bool = Option(
        False,
        "--force",
        help=(
            "Force the task to start from the beginning despite the presence of a"
            " pre-existing incomplete result file and overwrite that file."
        ),
    ),
    instance: str = Option(
        "prod",
        "--instance",
        help="The Canvas instance to use.",
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """Generate reports"""
    report_main(report_type, term, force, instance, verbose)


@app.command()
def roles(
    permission: str = Option(
        "view_statistics", "--permission", help="The permission to check"
    ),
    instance: str = Option(
        Instance.PRODUCTION.value,
        "--instance",
        help="The Canvas instance to use.",
    ),
    verbose: bool = Option(
        False, "--verbose", help="Print out detailed information as the task runs."
    ),
):
    """Generate a report of role permissions."""
    roles_main(permission, instance, verbose)


@app.command()
def storage(
    increment_value: int = Option(
        1000, "--increment", help="The amount in MB to increase a course's storage."
    ),
    instance: str = Option(
        Instance.PRODUCTION.value, "--instance", help="The Canvas instance to use."
    ),
    force: bool = Option(
        False,
        "--force",
        help="Start the task from the beginning, ignoring already processed courses",
    ),
    force_report: bool = Option(
        False,
        "--force-report",
        help="Generate a new report instead of using a cached one.",
    ),
    verbose: bool = Option(
        False,
        "--verbose",
        help="Print detailed information to the console as the task runs.",
    ),
):
    """
    Increases the storage quota for each course that currently uses 79% or more
    of its current storage allotment.
    """
    storage_main(increment_value, instance, force, force_report, verbose)


@app.command()
def tool(
    tool: str = Argument(
        ...,
        help=(
            "The Canvas external tool you wish to work with. Must match the tool's"
            " Canvas tab's label, or id if using --id."
        ),
    ),
    term: str = Option(
        CURRENT_YEAR_AND_TERM,
        "--term-name",
        help="The display name of the term for the report",
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
    instance_name: str = Option(
        Instance.PRODUCTION.value,
        "--instance",
        help="The Canvas instance to use.",
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
    force_report: bool = Option(
        False,
        "--force-report",
        help="Force a new report to be generated rather than use a cahced one.",
    ),
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help=(
            "Clear the list of courses already processed for the term(s). Only runs if"
            " '--enable' is also used."
        ),
    ),
    account_id: str = Option(
        None, "--account-id", help="Operate on the specified sub-account only."
    ),
):
    """
    Returns a list of courses with TOOL enabled or enables TOOL for a list of
    courses if using '--enable'.
    """
    tool_main(
        tool,
        term,
        use_id,
        enable,
        instance_name,
        verbose,
        new,
        force,
        force_report,
        clear_processed,
        account_id,
    )


@app.command()
def update_term(
    account: int = Option(
        PENN_CANVAS_MAIN_ACCOUNT_ID,
        help=(
            "The Canvas Sub-account ID whose course's enrollment terms need to be"
            " changed"
        ),
    ),
    current_term: str = Option(
        "",
        help="The existing enrollment term value to be updated",
    ),
    new_term: str = Option(
        "Penn Term",
        help="The new enrollment term value to udpate courses with",
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
    Update enrollment term for courses in specified sub-account.
    """
    update_term_main(account, current_term, new_term, test)


@app.command()
def usage_count(tool: str = Option("turnitin", help="The tool to count usage for")):
    """Generate a report of tool usage."""
    usage_count_main(tool)
