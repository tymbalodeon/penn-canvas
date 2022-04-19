from pathlib import Path
from time import sleep
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from requests.api import post
from typer import Option, Typer, echo

from penn_canvas.api import get_course, get_instance_option, validate_instance_name
from penn_canvas.helpers import (
    BASE_PATH,
    COURSE_IDS,
    CURRENT_YEAR_AND_TERM,
    FORCE_REPORT,
    VERBOSE,
    create_directory,
    get_course_ids_from_input,
    switch_logger_file,
)
from penn_canvas.report import get_course_ids_from_reports
from penn_canvas.style import color, print_item

from .announcements import fetch_announcements, unpack_announcements
from .assignments.assignments import fetch_assignments, unpack_assignments
from .content import CONTENT_TAR_STEM, fetch_content, unpack_content
from .discussions import fetch_discussions, unpack_discussions
from .grades import fetch_grades, unpack_grades
from .groups import fetch_groups, unpack_groups
from .helpers import format_name
from .modules import fetch_modules, unpack_modules
from .pages import fetch_pages, unpack_pages
from .quizzes.quizzes import fetch_quizzes, unpack_quizzes
from .rubrics import fetch_rubrics, unpack_rubrics
from .syllabus import fetch_syllabus, unpack_syllabus

archive_app = Typer(
    no_args_is_help=True,
    help="Archive Canvas courses",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)
content = Option(None, "--content/--no-content", help="Include/exclude course content")
announcements = Option(
    None,
    "--announcements/--no-announcements",
    help="Include/exclude course announcements",
)
groups = Option(None, "--groups/--no-groups", help="Include/exclude course groups")
modules = Option(None, "--modules/--no-modeules", help="Include/exclude course modules")

pages = Option(None, "--pages/--no-pages", help="Include/exclude course pages")
syllabus = Option(
    None, "--syllabus/--no-syllabus", help="Include/exclude course syllabus"
)
assignments = Option(
    None, "--assignments/--no-assignments", help="Include/exclude course assignments"
)
discussions = Option(
    None, "--discussions/--no-discussions", help="Include/exclude course discussions"
)
grades = Option(None, "--grades/--no-grades", help="Include/exclude course grades")
rubrics = Option(None, "--rubrics/--no-rubrics", help="Include/exclude course rubrics")
quizzes = Option(None, "--quizzes/--no-quizzes", help="Include/exclude course quizzes")
COMMAND_PATH = create_directory(BASE_PATH / "Archive")
COMPRESSED_COURSES = create_directory(COMMAND_PATH / "Compressed Courses")
UNPACKED_COURSES = create_directory(COMMAND_PATH / "Courses")
LOGS = create_directory(COMMAND_PATH / "Logs")


def format_course_name(course: Course) -> str:
    return f"{format_name(course.name)} ({course.id})"


def print_course(index: int, total: int, course_name: str):
    print_item(index, total, color(course_name, "blue"))


def should_run_option(option: Optional[bool], use_all: bool) -> bool:
    return option if isinstance(option, bool) else use_all


@archive_app.command()
def fetch(
    course_ids: Optional[list[int]] = COURSE_IDS,
    terms: list[str] = Option([CURRENT_YEAR_AND_TERM], "--term", help="Term name"),
    instance_name: str = get_instance_option(),
    content: Optional[bool] = content,
    announcements: Optional[bool] = announcements,
    groups: Optional[bool] = groups,
    modules: Optional[bool] = modules,
    pages: Optional[bool] = pages,
    syllabus: Optional[bool] = syllabus,
    assignments: Optional[bool] = assignments,
    discussions: Optional[bool] = discussions,
    grades: Optional[bool] = grades,
    rubrics: Optional[bool] = rubrics,
    quizzes: Optional[bool] = quizzes,
    unpack: bool = Option(False, "--unpack", help="Unpack compressed files"),
    force_report: bool = FORCE_REPORT,
    verbose: bool = VERBOSE,
):
    """
    Archive Canvas courses

    Options with both "include" and "exclude" flags will all be included if none
    of the flags are specified.
    """
    archive_all = not any(
        [
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
        ]
    )
    instance = validate_instance_name(instance_name, verbose=True)
    switch_logger_file(LOGS, "archive", instance.name)
    if not course_ids:
        courses = get_course_ids_from_reports(terms, instance, force_report, verbose)
    else:
        courses = get_course_ids_from_input(course_ids)
    total = len(courses)
    for index, course_id in enumerate(courses):
        course = get_course(course_id, include=["syllabus_body"], instance=instance)
        course_name = format_course_name(course)
        print_course(index, total, course_name)
        compress_path = create_directory(COMPRESSED_COURSES / course_name)
        unpack_path = UNPACKED_COURSES / course_name
        assignment_objects: list[Assignment] = list()
        args = (course, compress_path, unpack_path, unpack)
        if should_run_option(content, archive_all):
            fetch_content(*args, instance, verbose)
        if should_run_option(announcements, archive_all):
            fetch_announcements(*args, verbose)
        if should_run_option(modules, archive_all):
            fetch_modules(*args, instance, verbose)
        if should_run_option(pages, archive_all):
            fetch_pages(*args, verbose)
        if should_run_option(syllabus, archive_all):
            fetch_syllabus(*args, verbose)
        if should_run_option(assignments, archive_all):
            assignment_objects = fetch_assignments(*args, instance, verbose)
        if should_run_option(groups, archive_all):
            fetch_groups(*args, verbose)
        if should_run_option(discussions, archive_all):
            fetch_discussions(*args, instance, verbose)
        if should_run_option(grades, archive_all):
            fetch_grades(*args, assignment_objects, instance, verbose)
        if should_run_option(rubrics, archive_all):
            fetch_rubrics(*args, verbose)
        if should_run_option(quizzes, archive_all):
            fetch_quizzes(*args, instance, verbose)
        echo("COMPELTE")


@archive_app.command()
def unpack(
    course_ids: Optional[list[int]] = COURSE_IDS,
    terms: list[str] = Option([CURRENT_YEAR_AND_TERM], "--term", help="Term name"),
    instance_name: str = get_instance_option(),
    content: Optional[bool] = content,
    announcements: Optional[bool] = announcements,
    groups: Optional[bool] = groups,
    modules: Optional[bool] = modules,
    pages: Optional[bool] = pages,
    syllabus: Optional[bool] = syllabus,
    assignments: Optional[bool] = assignments,
    discussions: Optional[bool] = discussions,
    grades: Optional[bool] = grades,
    rubrics: Optional[bool] = rubrics,
    quizzes: Optional[bool] = quizzes,
    force_report: bool = FORCE_REPORT,
    verbose: bool = VERBOSE,
):
    """
    Unpack archived Canvas courses

    Options with both "include" and "exclude" flags will all be included if none
    of the flags are specified.
    """
    unpack_all = not any(
        [
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
        ]
    )
    instance = validate_instance_name(instance_name, verbose=True)
    switch_logger_file(LOGS, "archive", instance.name)
    if not course_ids:
        courses = get_course_ids_from_reports(terms, instance, force_report, verbose)
    else:
        courses = get_course_ids_from_input(course_ids)
    total = len(courses)
    for index, course_id in enumerate(courses):
        course = get_course(course_id, instance=instance)
        course_name = format_course_name(course)
        if verbose:
            print_course(index, total, course_name)
        compress_path = create_directory(COMPRESSED_COURSES / course_name)
        unpack_path = create_directory(UNPACKED_COURSES / course_name)
        args = (compress_path, unpack_path, verbose)
        if should_run_option(content, unpack_all):
            unpack_content(*args)
        if should_run_option(announcements, unpack_all):
            unpack_announcements(*args)
        if should_run_option(modules, unpack_all):
            unpack_modules(*args)
        if should_run_option(pages, unpack_all):
            unpack_pages(*args)
        if should_run_option(syllabus, unpack_all):
            unpack_syllabus(*args)
        if should_run_option(assignments, unpack_all):
            unpack_assignments(*args)
        if should_run_option(groups, unpack_all):
            unpack_groups(*args)
        if should_run_option(discussions, unpack_all):
            unpack_discussions(*args)
        if should_run_option(grades, unpack_all):
            unpack_grades(*args)
        if should_run_option(rubrics, unpack_all):
            unpack_rubrics(*args)
        if should_run_option(quizzes, unpack_all):
            unpack_quizzes(compress_path, unpack_path, verbose)
        echo("COMPELTE")


@archive_app.command()
def restore(
    course_ids: Optional[list[int]] = COURSE_IDS,
    terms: list[str] = Option([CURRENT_YEAR_AND_TERM], "--term", help="Term name"),
    instance_name: str = get_instance_option(),
    force_report: bool = FORCE_REPORT,
    verbose: bool = VERBOSE,
):
    instance = validate_instance_name(instance_name, verbose=True)
    switch_logger_file(LOGS, "archive", instance.name)
    if not course_ids:
        courses = get_course_ids_from_reports(terms, instance, force_report, verbose)
    else:
        courses = get_course_ids_from_input(course_ids)
    total = len(courses)
    for index, course_id in enumerate(courses):
        content_file = next(
            path / CONTENT_TAR_STEM
            for path in Path(COMPRESSED_COURSES).iterdir()
            if path.is_dir() and str(course_id) in path.name
        )
        course = get_course(course_id, instance=instance)
        course_name = format_course_name(course)
        if verbose:
            print_course(index, total, course_name)
        content_migration = course.create_content_migration(
            "common_cartridge_importer",
            pre_attachment={
                "name": content_file.name,
                "size": content_file.stat().st_size,
            },
        )
        echo(f") Uploading {course} content file...")
        with open(content_file, "rb") as content:
            upload_url = content_migration.pre_attachment["upload_url"]
            data = dict()
            for key, value in content_migration.pre_attachment["upload_params"].items():
                data[key] = value
            status_code = post(
                upload_url, data=data, files={"file": content}
            ).status_code
        if not status_code == 201:
            echo(color("ERROR: file not uploaded", "red"))
            return
        content_migration = course.get_content_migration(content_migration)
        echo(") Running migration...")
        while (
            content_migration.get_progress().workflow_state == "queued"
            or content_migration.get_progress().workflow_state == "running"
        ):
            echo("\t* Migration running...")
            sleep(8)
        echo("MIGRATION COMPLETE")
