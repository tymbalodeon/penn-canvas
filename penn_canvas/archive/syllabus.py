from pathlib import Path

from canvasapi.course import Course
from typer import echo

from penn_canvas.helpers import create_directory

from .helpers import strip_tags


def archive_syllabus(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting syllabus...")
    syllabus_path = create_directory(course_path / "Syllabus")
    syllabus = course.syllabus_body
    if syllabus:
        syllabus = strip_tags(syllabus)
        with open(syllabus_path / "syllabus.txt", "w") as syllabus_file:
            syllabus_file.write(syllabus)
        if verbose:
            echo(f"SYLLABUS: {syllabus}")
