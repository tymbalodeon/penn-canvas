from html.parser import HTMLParser
from io import StringIO
from typing import Optional

from canvasapi.assignment import Assignment
from typer import echo

from penn_canvas.api import get_course, validate_instance_name
from penn_canvas.helpers import BASE_PATH, create_directory, switch_logger_file
from penn_canvas.style import color

from .announcements import archive_announcements
from .assignments import archive_assignments
from .content import archive_content
from .discussions import archive_discussions
from .grades import archive_grades
from .groups import archive_groups
from .modules import archive_modules
from .pages import archive_pages
from .quizzes import archive_quizzes
from .rubrics import archive_rubrics
from .syllabus import archive_syllabus

COMMAND_PATH = create_directory(BASE_PATH / "Archive")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")
PICKLE_COMPRESSION_TYPE = "zip"


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html: str) -> str:
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()


def format_name(name: str) -> str:
    return name.strip().replace("/", "-").replace(":", "-")


def format_display_text(text: str, limit=50) -> str:
    truncated = len(text) > limit
    text = text.replace("\n", " ").replace("\t", " ")[:limit]
    if truncated:
        final_character = text[-1]
        while final_character == " " or final_character == ".":
            text = text[:-1]
            final_character = text[-1]
        text = f"{text}..."
    return text


def should_run_option(option: Optional[bool], archive_all: bool) -> bool:
    return option if isinstance(option, bool) else archive_all


def archive_main(
    course_id: int,
    instance_name: str,
    verbose: bool,
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
    quizzes: Optional[bool],
    rubrics: Optional[bool],
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
            quizzes,
            rubrics,
        ]
    )
    instance = validate_instance_name(instance_name)
    switch_logger_file(LOGS, "archive", instance.name)
    course = get_course(course_id, include=["syllabus_body"], instance=instance)
    course_name = f"{format_name(course.name)} ({course.id})"
    echo(f") Archiving course: {color(course_name, 'blue')}...")
    course_path = create_directory(RESULTS / course_name)
    assignment_objects: list[Assignment] = list()
    if should_run_option(content, archive_all):
        archive_content(course, course_path, instance, verbose)
    if should_run_option(announcements, archive_all):
        archive_announcements(course, course_path, verbose)
    if should_run_option(modules, archive_all):
        archive_modules(course, course_path, verbose)
    if should_run_option(pages, archive_all):
        archive_pages(course, course_path, verbose)
    if should_run_option(syllabus, archive_all):
        archive_syllabus(course, course_path, verbose)
    if should_run_option(assignments, archive_all):
        assignment_objects = archive_assignments(course, course_path, instance, verbose)
    if should_run_option(groups, archive_all):
        archive_groups(course, course_path, instance, verbose)
    if should_run_option(discussions, archive_all):
        archive_discussions(course, course_path, use_timestamp, instance, verbose)
    if should_run_option(grades, archive_all):
        archive_grades(course, course_path, assignment_objects, instance, verbose)
    if should_run_option(quizzes, archive_all):
        archive_quizzes(course, course_path, instance, verbose)
    if should_run_option(rubrics, archive_all):
        archive_rubrics(course, course_path, verbose)
    echo("COMPELTE")
