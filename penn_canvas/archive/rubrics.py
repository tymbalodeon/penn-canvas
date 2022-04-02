from pathlib import Path
from typing import Optional

from canvasapi.course import Course
from canvasapi.rubric import Rubric
from pandas import DataFrame, concat, read_csv
from typer import echo, progressbar

from penn_canvas.helpers import create_directory, print_task_complete_message
from penn_canvas.style import color, print_item

from .helpers import COMPRESSION_TYPE, print_unpacked_file

RUBRICS_COMPRESSED_FILE = f"rubrics.{COMPRESSION_TYPE}"


def get_rubrics(course: Course) -> tuple[list[Rubric], int]:
    echo(") Finding rubrics...")
    rubrics = list(course.get_rubrics())
    return rubrics, len(rubrics)


def process_criterion_rating(rating):
    points = rating["points"]
    description = rating["description"]
    long_description = rating["long_description"] or ""
    return f"{points} {description} {long_description}"


def process_criterion(criterion, rubric_id, title):
    description = criterion["description"]
    ratings = criterion["ratings"]
    ratings = [process_criterion_rating(rating) for rating in ratings]
    ratings = " / ".join(ratings)
    points = criterion["points"]
    return [rubric_id, title, description, ratings, points]


def archive_rubric(
    rubric: Rubric,
    verbose: bool,
    index=0,
    total=0,
):
    title = rubric.title.strip()
    if verbose:
        print_item(index, total, color(title))
    criteria = [
        process_criterion(criterion, rubric.id, title) for criterion in rubric.data
    ]
    return DataFrame(
        criteria, columns=["Rubric ID", "Rubric Title", "Criteria", "Ratings", "Pts"]
    )


def unpack_rubrics(
    compress_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo(") Unpacking announcements...")
    compressed_file = compress_path / RUBRICS_COMPRESSED_FILE
    if not compressed_file.is_file():
        return None
    data_frame = read_csv(compressed_file)
    rubric_ids = data_frame["Rubric ID"].unique()
    rubrics = [
        data_frame[data_frame["Rubric ID"] == rubric_id] for rubric_id in rubric_ids
    ]
    rubrics_path = create_directory(unpack_path / "Rubrics")
    total = len(rubrics)
    for index, rubric in enumerate(rubrics):
        title = next(iter(rubric["Rubric Title"].tolist()), "")
        rubric_path = rubrics_path / f"{title}.csv"
        rubric.to_csv(rubric_path, index=False)
        if verbose:
            print_item(index, total, color(title))
            print_task_complete_message(rubrics_path)
    return rubrics_path


def archive_rubrics(
    course: Course, compress_path: Path, unpack_path: Path, unpack: bool, verbose: bool
):
    echo(") Exporting rubrics...")
    rubric_objects, rubric_total = get_rubrics(course)
    if verbose:
        total = len(rubric_objects)
        rubrics = [
            archive_rubric(rubric, verbose, index, total)
            for index, rubric in enumerate(rubric_objects)
        ]
    else:
        with progressbar(rubric_objects, length=rubric_total) as progress:
            rubrics = [archive_rubric(rubric, verbose) for rubric in progress]
    rubrics_path = compress_path / RUBRICS_COMPRESSED_FILE
    rubric_data = concat(rubrics)
    rubric_data.to_csv(rubrics_path, index=False)
    if unpack:
        unpacked_path = unpack_rubrics(compress_path, unpack_path, verbose=False)
        if verbose:
            print_unpacked_file(unpacked_path)
    return rubric_objects
