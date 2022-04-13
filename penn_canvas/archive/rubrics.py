from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from canvasapi.rubric import Rubric
from pandas import DataFrame, concat, read_csv
from typer import echo, progressbar

from penn_canvas.helpers import create_directory, print_task_complete_message
from penn_canvas.style import color, print_item

from .helpers import CSV_COMPRESSION_TYPE, print_unpacked_file

RUBRICS_COMPRESSED_FILE = f"rubrics.{CSV_COMPRESSION_TYPE}"
RUBRIC_ID = "Rubric ID"
RUBRIC_TITLE = "Rubric Title"


def get_criterion_rating(rating: dict) -> str:
    points = rating["points"]
    description = rating["description"]
    long_description = rating["long_description"] or ""
    return f"{points} {description} {long_description}"


def get_criterion(criterion: dict, rubric_id: str, title: str) -> list[str]:
    description = criterion["description"]
    ratings = criterion["ratings"]
    ratings = [get_criterion_rating(rating) for rating in ratings]
    ratings = " / ".join(ratings)
    points = criterion["points"]
    return [rubric_id, title, description, ratings, points]


def get_rubric(
    rubric: Rubric,
    verbose: bool,
    index=0,
    total=0,
) -> DataFrame:
    title = rubric.title.strip()
    if verbose:
        print_item(index, total, color(title))
    criteria = [get_criterion(criterion, rubric.id, title) for criterion in rubric.data]
    return DataFrame(
        criteria, columns=[RUBRIC_ID, "Rubric Title", "Criteria", "Ratings", "Pts"]
    )


def unpack_rubrics(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking announcements...")
    compressed_file = compress_path / RUBRICS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    rubrics_data = read_csv(compressed_file)
    rubric_ids = rubrics_data[RUBRIC_ID].unique()
    rubrics = [
        rubrics_data[rubrics_data[RUBRIC_ID] == rubric_id] for rubric_id in rubric_ids
    ]
    rubrics_path = create_directory(unpack_path / "Rubrics")
    total = len(rubrics)
    for index, rubric in enumerate(rubrics):
        title = next(iter(rubric[RUBRIC_TITLE].tolist()), "")
        rubric_path = rubrics_path / f"{title}.csv"
        rubric.to_csv(rubric_path, index=False)
        if verbose:
            print_item(index, total, color(title))
            print_task_complete_message(rubrics_path)
    return rubrics_path


def fetch_rubrics(
    course: Course, compress_path: Path, unpack_path: Path, unpack: bool, verbose: bool
):
    echo(") Exporting rubrics...")
    rubric_objects = list(course.get_rubrics())
    total = len(rubric_objects)
    if verbose:
        rubrics = [
            get_rubric(rubric, verbose, index, total)
            for index, rubric in enumerate(rubric_objects)
        ]
    else:
        with progressbar(rubric_objects, length=total) as progress:
            rubrics = [get_rubric(rubric, verbose) for rubric in progress]
    rubric_data = concat(rubrics)
    rubrics_path = compress_path / RUBRICS_COMPRESSED_FILE
    rubric_data.to_csv(rubrics_path, index=False)
    if unpack:
        unpacked_path = unpack_rubrics(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
