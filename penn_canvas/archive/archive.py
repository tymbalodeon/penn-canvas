from pathlib import Path
from time import sleep
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.rubric import Rubric
from requests.api import post
from typer import echo

from penn_canvas.api import get_canvas, get_course, validate_instance_name
from penn_canvas.helpers import (
    BASE_PATH,
    create_directory,
    get_course_ids_from_input,
    switch_logger_file,
)
from penn_canvas.report import get_course_ids_from_reports
from penn_canvas.style import color, print_item

from .announcements import archive_announcements
from .assignments import archive_assignments
from .content import CONTENT_DIRECTORY_NAME, archive_content
from .discussions import archive_discussions
from .grades import archive_grades
from .groups import archive_groups
from .helpers import format_name, should_run_option
from .modules import archive_modules
from .pages import archive_pages
from .quizzes import archive_quizzes
from .rubrics import archive_rubrics
from .syllabus import archive_syllabus

COMMAND_PATH = create_directory(BASE_PATH / "Archive")
COMPRESSED_COURSES = create_directory(COMMAND_PATH / "Compressed Courses")
UNPACKED_COURSES = create_directory(COMMAND_PATH / "Courses")
LOGS = create_directory(COMMAND_PATH / "Logs")


def restore_course(course, instance):
    content_file = next(
        path / CONTENT_DIRECTORY_NAME
        for path in Path(COMPRESSED_COURSES).iterdir()
        if path.is_dir() and str(course) in path.name
    )
    canvas_course = get_canvas(instance).get_course(course)
    content_migration = canvas_course.create_content_migration(
        "common_cartridge_importer",
        pre_attachment={"name": content_file.name, "size": content_file.stat().st_size},
    )
    echo(f") Uploading {canvas_course} content file...")
    with open(content_file, "rb") as content:
        upload_url = content_migration.pre_attachment["upload_url"]
        data = dict()
        for key, value in content_migration.pre_attachment["upload_params"].items():
            data[key] = value
        status_code = post(upload_url, data=data, files={"file": content}).status_code
    if not status_code == 201:
        echo(color("ERROR: file not uploaded", "red"))
        return
    content_migration = canvas_course.get_content_migration(content_migration)
    echo(") Running migration...")
    while (
        content_migration.get_progress().workflow_state == "queued"
        or content_migration.get_progress().workflow_state == "running"
    ):
        echo("\t* Migration running...")
        sleep(8)
    echo("MIGRATION COMPLETE")


def archive_main(
    course_ids: Optional[int | list[int]],
    terms: str | list[str],
    instance_name: str,
    use_timestamp: bool,
    content: Optional[bool],
    announcements: Optional[bool],
    modules: Optional[bool],
    pages: Optional[bool],
    syllabus: Optional[bool],
    assignments: Optional[bool],
    groups: Optional[bool],
    discussions: Optional[bool],
    grades: Optional[bool],
    rubrics: Optional[bool],
    quizzes: Optional[bool],
    unpack: bool,
    force_report: bool,
    verbose: bool,
):
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
    for index, canvas_id in enumerate(courses):
        course = get_course(canvas_id, include=["syllabus_body"], instance=instance)
        course_name = f"{format_name(course.name)} ({course.id})"
        print_item(index, total, color(course_name, "blue"))
        compress_path = create_directory(COMPRESSED_COURSES / course_name)
        unpack_path = create_directory(UNPACKED_COURSES / course_name)
        assignment_objects: list[Assignment] = list()
        rubric_objects: list[Rubric] = list()
        if should_run_option(content, archive_all):
            archive_content(course, compress_path, instance, verbose)
        if should_run_option(announcements, archive_all):
            archive_announcements(course, compress_path, unpack_path, unpack, verbose)
        if should_run_option(modules, archive_all):
            archive_modules(course, compress_path, verbose)
        if should_run_option(pages, archive_all):
            archive_pages(course, compress_path, unpack_path, unpack, verbose)
        if should_run_option(syllabus, archive_all):
            archive_syllabus(course, compress_path, unpack_path, unpack, verbose)
        if should_run_option(assignments, archive_all):
            assignment_objects = archive_assignments(
                course, compress_path, instance, verbose
            )
        if should_run_option(groups, archive_all):
            archive_groups(course, compress_path, instance, verbose)
        if should_run_option(discussions, archive_all):
            archive_discussions(course, compress_path, use_timestamp, instance, verbose)
        if should_run_option(grades, archive_all):
            archive_grades(course, compress_path, assignment_objects, instance, verbose)
        if should_run_option(rubrics, archive_all):
            rubric_objects = archive_rubrics(
                course, compress_path, unpack_path, unpack, verbose
            )
        if should_run_option(quizzes, archive_all):
            archive_quizzes(course, compress_path, rubric_objects, verbose)
        echo("COMPELTE")
