from pathlib import Path
from shutil import make_archive, rmtree
from typing import Optional

from canvasapi.course import Course
from typer import echo

from penn_canvas.api import Instance
from penn_canvas.archive.helpers import TAR_COMPRESSION_TYPE, TAR_EXTENSION
from penn_canvas.helpers import create_directory

from .assignment_descriptions import fetch_descriptions, unpack_descriptions
from .comments import fetch_submission_comments
from .submissions import fetch_submissions, unpack_submissions

ASSIGNMENTS_TAR_STEM = "assignments"
UNPACK_ASSIGNMENTS_DIRECTORY = ASSIGNMENTS_TAR_STEM.title()
ASSIGNMENTS_TAR_NAME = f"{ASSIGNMENTS_TAR_STEM}.{TAR_EXTENSION}"


def unpack_assignments(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking assignments...")
    archive_tar_path = compress_path / ASSIGNMENTS_TAR_NAME
    if not archive_tar_path.is_file():
        return None
    unpack_path = create_directory(unpack_path / UNPACK_ASSIGNMENTS_DIRECTORY)
    unpack_descriptions(compress_path, archive_tar_path, unpack_path, verbose)
    unpack_submissions(compress_path, archive_tar_path, unpack_path, verbose)
    return unpack_path


def fetch_assignments(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Fetching assignments...")
    assignments_path = create_directory(compress_path / ASSIGNMENTS_TAR_STEM)
    archive_tar_path = compress_path / ASSIGNMENTS_TAR_NAME
    unpack_path = create_directory(unpack_path / UNPACK_ASSIGNMENTS_DIRECTORY)
    assignments = list(course.get_assignments())
    total = len(assignments)
    fetch_descriptions(
        assignments,
        assignments_path,
        archive_tar_path,
        unpack_path,
        unpack,
        verbose,
        total,
    )
    fetch_submissions(
        assignments, assignments_path, unpack_path, unpack, instance, verbose, total
    )
    fetch_submission_comments(assignments, assignments_path, verbose, total)
    assignments_directory = str(assignments_path)
    make_archive(
        assignments_directory, TAR_COMPRESSION_TYPE, root_dir=assignments_directory
    )
    rmtree(assignments_path)
    return assignments
