from pathlib import Path

from canvasapi.course import Course
from canvasapi.rubric import Rubric
from pandas import DataFrame
from typer import echo, progressbar

from penn_canvas.api import collect
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def get_rubrics(course: Course) -> tuple[list[Rubric], int]:
    echo(") Finding rubrics...")
    rubrics = collect(course.get_rubrics())
    return rubrics, len(rubrics)


def process_criterion_rating(rating):
    points = rating["points"]
    description = rating["description"]
    long_description = rating["long_description"] or ""
    return f"{points} {description} {long_description}"


def process_criterion(criterion):
    description = criterion["description"]
    ratings = criterion["ratings"]
    ratings = [process_criterion_rating(rating) for rating in ratings]
    ratings = " / ".join(ratings)
    points = criterion["points"]
    return [description, ratings, points]


def archive_rubric(
    rubric: Rubric, course_directory: Path, verbose: bool, index=0, total=0
):
    title = rubric.title.strip()
    if verbose:
        print_item(index, total, color(title))
    rubric_directory = create_directory(course_directory / "Rubrics")
    rubric_path = rubric_directory / f"{title}.csv"
    criteria = [process_criterion(criterion) for criterion in rubric.data]
    data_frame = DataFrame(criteria, columns=["Criteria", "Ratings", "Pts"])
    data_frame.to_csv(rubric_path, index=False)


def archive_rubrics(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting rubrics...")
    rubric_objects, rubric_total = get_rubrics(course)
    if verbose:
        total = len(rubric_objects)
        for index, rubric in enumerate(rubric_objects):
            archive_rubric(rubric, course_path, verbose, index, total)
    else:
        with progressbar(rubric_objects, length=rubric_total) as progress:
            for rubric in progress:
                archive_rubric(rubric, course_path, verbose)
