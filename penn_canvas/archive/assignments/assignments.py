from pathlib import Path
from shutil import make_archive, rmtree, unpack_archive
from typing import Optional

from canvasapi.course import Course
from typer import echo

from penn_canvas.api import Instance
from penn_canvas.archive.helpers import TAR_COMPRESSION_TYPE, TAR_EXTENSION
from penn_canvas.helpers import create_directory

from .comments import archive_submission_comments
from .descriptions import fetch_descriptions, unpack_descriptions
from .submissions import archive_submissions

ASSIGNMENTS_TAR_STEM = "assignments"
UNPACK_ASSIGNMENTS_DIRECTORY = ASSIGNMENTS_TAR_STEM.title()
ASSIGNMENTS_TAR_NAME = f"{ASSIGNMENTS_TAR_STEM}.{TAR_EXTENSION}"


def unpack_assignments(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking assignments...")
    archive_file = compress_path / ASSIGNMENTS_TAR_NAME
    if not archive_file.is_file():
        return None
    unpack_path = create_directory(unpack_path / UNPACK_ASSIGNMENTS_DIRECTORY)
    unpack_archive(archive_file, compress_path)
    unpack_descriptions(compress_path, unpack_path, verbose)
    return unpack_path


def fetch_assignments(
    course: Course,
    course_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting assignments...")
    assignments_path = create_directory(course_path / ASSIGNMENTS_TAR_STEM)
    unpack_path = create_directory(unpack_path / UNPACK_ASSIGNMENTS_DIRECTORY)
    assignments = list(course.get_assignments())
    total = len(assignments)
    fetch_descriptions(
        assignments, assignments_path, unpack_path, unpack, verbose, total
    )
    archive_submissions(
        assignments, instance, assignments_path, unpack_path, unpack, verbose, total
    )
    archive_submission_comments(assignments, assignments_path, verbose, total)
    assignments_files = str(assignments_path)
    make_archive(assignments_files, TAR_COMPRESSION_TYPE, root_dir=assignments_files)
    rmtree(assignments_path)
    return assignments
