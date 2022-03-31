from pathlib import Path

from canvasapi.course import Course
from pandas import DataFrame, read_csv
from typer import echo

from penn_canvas.helpers import print_task_complete_message, write
from penn_canvas.style import color

from .helpers import COMPRESSION_TYPE, format_display_text, strip_tags

SYLLABUS_COMPRESSION_FILE = f"syllabus.{COMPRESSION_TYPE}"


def display_syllabus(syllabus):
    echo(f"{color(format_display_text(syllabus, limit=60), 'cyan')}")


def unpack_syllabus(course_path: Path, verbose: bool):
    echo(") Unpacking syllabus...")
    compressed_file = course_path / SYLLABUS_COMPRESSION_FILE
    if not compressed_file.is_file():
        return
    data_frame = read_csv(course_path / SYLLABUS_COMPRESSION_FILE)
    syllabus = next(iter(data_frame["syllabus"].tolist()), "")
    syllabus_path = course_path / "Syllabus.txt"
    write(syllabus_path, syllabus)
    if verbose:
        display_syllabus(syllabus)
        print_task_complete_message(syllabus_path)


def archive_syllabus(course: Course, course_path: Path, unpack: bool, verbose: bool):
    echo(") Exporting syllabus...")
    syllabus = course.syllabus_body
    if syllabus:
        syllabus = strip_tags(syllabus)
        syllabus_data = DataFrame([syllabus], columns=["syllabus"])
        syllabus_file = course_path / SYLLABUS_COMPRESSION_FILE
        syllabus_data.to_csv(syllabus_file, index=False)
        if verbose:
            display_syllabus(syllabus)
        if unpack:
            unpack_syllabus(course_path, verbose=False)
