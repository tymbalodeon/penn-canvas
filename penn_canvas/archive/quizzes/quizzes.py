from pathlib import Path
from shutil import make_archive, rmtree

from canvasapi.course import Course
from typer import echo

from penn_canvas.api import Instance
from penn_canvas.archive.helpers import TAR_COMPRESSION_TYPE, TAR_EXTENSION
from penn_canvas.helpers import create_directory

from .descriptions import get_descriptions
from .questions import get_all_quiz_questions
from .responses import get_all_quiz_responses
from .scores import get_all_submission_scores

QUIZZES_TAR_STEM = "quizzes"
UNPACK_QUIZZES_DIRECTORY = QUIZZES_TAR_STEM.title()
QUIZZES_TAR_NAME = f"{QUIZZES_TAR_STEM}.{TAR_EXTENSION}"


def unpack_quizzes(compress_path: Path, unpack_path: Path, verbose: bool):
    echo(f"{compress_path}, {unpack_path}, {verbose}")


def fetch_quizzes(
    course: Course,
    compress_path: Path,
    unpack_path: Path,
    unpack: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Fetching quizzes...")
    quizzes_path = create_directory(compress_path / QUIZZES_TAR_STEM)
    unpack_path = create_directory(unpack_path / UNPACK_QUIZZES_DIRECTORY)
    quizzes = list(course.get_quizzes())
    get_descriptions(compress_path, quizzes, verbose)
    get_all_quiz_questions(quizzes, compress_path)
    get_all_submission_scores(quizzes, compress_path, instance)
    get_all_quiz_responses(course, compress_path, instance, verbose)
    quizzes_directory = str(quizzes_path)
    make_archive(quizzes_directory, TAR_COMPRESSION_TYPE, root_dir=quizzes_directory)
    rmtree(quizzes_path)
