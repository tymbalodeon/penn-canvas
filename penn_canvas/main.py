from typing import Optional

from click.exceptions import Exit
from typer import Argument, Option, Typer, echo

from penn_canvas import __version__
from penn_canvas.blue_jeans import blue_jeans_main

from .api import Instance, get_instance_option
from .archive.archive import archive_app
from .browser import browser_main
from .bulk_enroll import bulk_enroll_main
from .check_enrollment import check_enrollment_main
from .config import print_config, write_config_options
from .count_poll_everywhere import count_poll_everywhere_main
from .count_quizzes import count_quizzes_main
from .count_sites import count_sites_main
from .course_shopping import course_shopping_main
from .email import email_main
from .find_users_by_email import find_users_by_email_main
from .helpers import (
    COURSE_IDS,
    CURRENT_DATE,
    CURRENT_YEAR_AND_TERM,
    FORCE,
    FORCE_REPORT,
    VERBOSE,
)
from .integrity import integrity_main
from .investigate import investigate_main
from .module import module_main
from .new_student_orientation import new_student_orientation_main
from .open_canvas_bulk_action import open_canvas_bulk_action_main
from .report import ReportType, report_main
from .roles import roles_main
from .storage import storage_main
from .tool import tool_main
from .update_term import update_term_main
from .usage_count import usage_count_main

app = Typer(
    no_args_is_help=True,
    help=f"penncanvas ({__version__}) - CLI for working with Penn's Canvas instances",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)
app.add_typer(archive_app, name="archive")


@app.command()
def blue_jeans(
    terms: list[str] = Option([CURRENT_YEAR_AND_TERM], "--term", help="Term name"),
    instance_name: str = get_instance_option(),
    account_id: Optional[int] = Option(None, "--account", help="Canvas account id"),
    verbose: bool = VERBOSE,
    force: bool = FORCE,
    force_report: bool = FORCE_REPORT,
):
    """Get Blue Jeans usage for a courses"""
    blue_jeans_main(terms, instance_name, account_id, verbose, force, force_report)


@app.command()
def browser(
    course_ids: Optional[list[int]] = COURSE_IDS,
    instance_name: str = get_instance_option(default=Instance.OPEN),
    force: bool = FORCE,
    verbose: bool = VERBOSE,
):
    """Report user browser data for Canvas courses"""
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
    input_file: bool = Option(True, "--no-input-file", help="Get terms from csv file"),
    dry_run: bool = Option(
        False,
        "--dry-run",
        help="Print courses for review without performing enrollment",
    ),
    instance_name=get_instance_option(default=Instance.TEST),
    check_errors: bool = Option(
        False, "--check-errors", help="Locate previous errors and re-attempt"
    ),
    clear_processed: bool = Option(
        False, "--clear-processed", help="Clear processed cache"
    ),
):
    """Enroll user into multiple courses"""
    bulk_enroll_main(
        user,
        sub_account,
        terms,
        input_file,
        dry_run,
        instance_name,
        check_errors,
        clear_processed,
    )


@app.command()
def check_enrollment(
    course: int = Option(..., "--course", help="Canvas course id"),
    date: str = Option(CURRENT_DATE.strftime("%Y-%m-%d"), help="Date (Y-M-D)"),
    instance_name: str = get_instance_option(),
    force: bool = FORCE,
    verbose: bool = VERBOSE,
):
    """Check enrollment"""
    check_enrollment_main(course, date, instance_name, force, verbose)


@app.command()
def config(
    update: bool = Option(False, "--update", help="Save new values to config file"),
    show_secrets: bool = Option(
        False, "--show-secrets", help="Display sensitive values on screen"
    ),
):
    """
    Manage config file

    To generate Canvas tokens, login to the appropriate Canvas instance using
    one of the urls above. Go to 'Account > Settings' and click 'New Access
    Token' under the 'Approved Integrations' heading. Enter a description in the
    'Purpose' field and click 'Generate Token'. Paste this token into the
    terminal when prompted by the `configure` command. You do not need to
    include all of them; for each one you will be asked whether you want to
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
    force: bool = FORCE,
    verbose: bool = VERBOSE,
):
    """Get Poll Everywhere usage for courses"""
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
    force: bool = FORCE,
    verbose: bool = VERBOSE,
):
    """Get quiz usage for courses"""
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
    instance_name=get_instance_option(),
):
    """Count course codes with a Canvas site"""
    count_sites_main(
        year_and_term, separate, graduate_course_minimum_number, instance_name
    )


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
    force: bool = FORCE,
    verbose: bool = VERBOSE,
    new: bool = Option(
        False,
        "--new",
        help=(
            "Process only newly added users, skipping previous users that encountered"
            " errors."
        ),
    ),
):
    """Enable/disable "Course Shopping" """
    course_shopping_main(test, disable, force, verbose, new)


@app.command()
def email(
    instance_name: str = get_instance_option(),
    new: bool = Option(
        False,
        "--new",
        help=(
            "Process only newly added users, skipping previous users that encountered"
            " errors."
        ),
    ),
    force: bool = FORCE,
    force_report: bool = FORCE_REPORT,
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
    verbose: bool = VERBOSE,
):
    """
    Activate unconfirmed email for users in supported schools

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
def find_users_by_email(emails_path: str = Argument("", help="Path to input csv")):
    """Find Canvas users by email"""
    find_users_by_email_main(emails_path)


@app.command()
def integrity(
    course_id: int = Option(..., "--course", help="Canvas course id"),
    user_ids: list[int] = Option(..., "--users", help="Canvas user id"),
    quiz_ids: list[int] = Option(..., "--quizzes", help="Canvas quiz id"),
    instance_name: str = get_instance_option(),
    skip_page_views: bool = Option(
        False,
        "--skip-page-views",
        help="Skip pulling page view data, which is time consuming.",
    ),
):
    """Get page views for students"""
    integrity_main(course_id, user_ids, quiz_ids, instance_name, skip_page_views)


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
    """Re-lock modules for course"""
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
    verbose: bool = VERBOSE,
    force: bool = FORCE,
    clear_processed: bool = Option(
        False,
        "--clear-processed",
        help="Clear the list of users already processed for the current year.",
    ),
):
    """
    Enroll students into Canvas groups for 'Thrive at Penn' site

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
    verbose: bool = VERBOSE,
    force: bool = FORCE,
    instance_name: str = get_instance_option(default=Instance.OPEN),
):
    """Process staff input files"""
    open_canvas_bulk_action_main(verbose, force, instance_name)


@app.command()
def report(
    report_type: str = Option(
        ReportType.PROVISIONING.value, "--report-type", help="Canvas AccountReport type"
    ),
    term: str = Option(
        CURRENT_YEAR_AND_TERM,
        "--term-name",
        help="The display name of the term for the report",
    ),
    force: bool = FORCE,
    instance: str = get_instance_option(),
    verbose: bool = VERBOSE,
):
    """Generate reports"""
    report_main(report_type, term, force, instance, verbose)


@app.command()
def roles(
    permission: str = Option(
        "view_statistics", "--permission", help="The permission to check"
    ),
    instance: str = get_instance_option(),
    verbose: bool = VERBOSE,
):
    """Get role permissions"""
    roles_main(permission, instance, verbose)


@app.command()
def storage(
    increment_value: int = Option(
        1000, "--increment", help="The amount in MB to increase a course's storage."
    ),
    instance: str = get_instance_option(),
    force: bool = FORCE,
    force_report: bool = FORCE_REPORT,
    verbose: bool = VERBOSE,
):
    """Increase storage quota for courses above 79% capacity"""
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
    enable: bool = Option(
        False,
        "--enable",
        help="Enable the specified tool rather than generate a usage report.",
    ),
    instance_name: str = get_instance_option(),
    verbose: bool = VERBOSE,
    new: bool = Option(
        False,
        "--new",
        help=(
            "Process only newly added courses, skipping previous courses that"
            " encountered errors."
        ),
    ),
    force: bool = FORCE,
    force_report: bool = FORCE_REPORT,
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
    """Enable tool or get tool usage for courses"""
    tool_main(
        tool,
        term,
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
    account_id: Optional[int] = Option(None, help="Canvas account id"),
    current_term_name: str = Option("", help="Term name"),
    new_term_name: str = Option("Penn Term", help="Term name"),
    instance_name=get_instance_option(),
):
    """Update enrollment term for courses"""
    update_term_main(account_id, current_term_name, new_term_name, instance_name)


@app.command()
def usage_count(tool: str = Option("turnitin", help="The tool to count usage for")):
    """Get tool usage for courses"""
    usage_count_main(tool)


def display_version(version: bool):
    if version:
        echo(f"penncanvas {__version__}")
        raise Exit()


@app.callback()
def version(
    version: bool = Option(
        False,
        "--version",
        "-V",
        callback=display_version,
        help="Display version number",
    )
):
    if version:
        return
