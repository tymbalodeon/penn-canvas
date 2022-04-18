from pathlib import Path
from shutil import make_archive, rmtree
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from typer import echo

from penn_canvas.api import Instance
from penn_canvas.archive.helpers import (
    TAR_COMPRESSION_TYPE,
    TAR_EXTENSION,
    print_unpacked_file,
)
from penn_canvas.helpers import create_directory

from .assignment_descriptions import fetch_descriptions, unpack_descriptions
from .comments import fetch_submission_comments, unpack_submission_comments
from .submissions import fetch_submissions, unpack_submissions

ASSIGNMENTS = "assignments"
ASSIGNMENTS_TAR_NAME = f"{ASSIGNMENTS}.{TAR_EXTENSION}"


def unpack_assignments(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking assignments...")
    archive_tar_path = compress_path / ASSIGNMENTS_TAR_NAME
    if not archive_tar_path.is_file():
        return None
    unpack_path = create_directory(unpack_path / ASSIGNMENTS.title())
    unpack_descriptions(compress_path, archive_tar_path, unpack_path, verbose)
    unpack_submissions(compress_path, archive_tar_path, unpack_path, verbose)
    unpack_submission_comments(compress_path, archive_tar_path, unpack_path, verbose)
    return unpack_path


def fetch_assignments(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
) -> list[Assignment]:
    echo(") Fetching assignments...")
    assignments = list(course.get_assignments())
    total = len(assignments)
    assignments_path = create_directory(compress_path / ASSIGNMENTS)
    fetch_descriptions(assignments, assignments_path, verbose, total)
    fetch_submissions(assignments, assignments_path, instance, verbose, total)
    fetch_submission_comments(assignments, assignments_path, verbose, total)
    make_archive_path = str(assignments_path)
    make_archive(make_archive_path, TAR_COMPRESSION_TYPE, root_dir=make_archive_path)
    if unpack:
        unpacked_path = unpack_assignments(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
    rmtree(assignments_path)
    return assignments
