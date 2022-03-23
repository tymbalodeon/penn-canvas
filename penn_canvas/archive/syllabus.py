from pathlib import Path

from canvasapi.course import Course
from penn_canas.helpers import create_directory
from typer import echo

from .archive import strip_tags


def archive_syllabus(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting syllabus...")
    syllabus_path = create_directory(course_path / "Syllabus")
    syllabus = strip_tags(course.syllabus_body)
    if syllabus:
        with open(syllabus_path / "syllabus.txt", "w") as syllabus_file:
            syllabus_file.write(syllabus)
        if verbose:
            echo(f"SYLLABUS: {syllabus}")
