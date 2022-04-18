from pathlib import Path
from tarfile import open as open_tarfile

from canvasapi.quiz import Quiz
from canvasapi.submission import Submission
from pandas import DataFrame, read_csv
from pandas.core.reshape.concat import concat
from typer import echo

from penn_canvas.api import Instance, get_user
from penn_canvas.archive.assignments.assignment_descriptions import QUIZ_ID
from penn_canvas.archive.helpers import format_name
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def get_submission_score(
    submission: Submission, points_possible: str, instance: Instance
):
    name = get_user(submission.user_id, instance=instance).name
    score = str(round(submission.score, 2)) if submission.score else ""
    return [name, score, points_possible]


def get_submission_scores(
    submissions: list[Submission], quiz: Quiz, instance: Instance
) -> DataFrame:
    points_possible = quiz.points_possible
    submission_scores = [
        [quiz.id, quiz.title]
        + get_submission_score(submission, points_possible, instance)
        for submission in submissions
    ]
    columns = ["Quiz ID", "Quiz Title", "Student", "Score", "Points Possible"]
    return DataFrame(submission_scores, columns=columns)


def unpack_quiz_scores(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
):
    echo("Unpacking quiz scores...")
    quizzes_tar_file = open_tarfile(archive_tar_path)
    quizzes_tar_file.extract("./scores.csv.gz", compress_path)
    unpacked_scores_path = compress_path / "scores.csv.gz"
    scores_data = read_csv(unpacked_scores_path)
    scores_data.fillna("", inplace=True)
    quiz_ids = scores_data[QUIZ_ID].unique()
    quizzes = [scores_data[scores_data[QUIZ_ID] == quiz_id] for quiz_id in quiz_ids]
    total = len(quizzes)
    for index, quiz in enumerate(quizzes):
        quiz = quiz.drop(columns=QUIZ_ID)
        quiz_title = next(iter(quiz["Quiz Title"].tolist()), "")
        quiz_title = format_name(quiz_title)
        if verbose:
            print_item(index, total, color(quiz_title))
        scores_path = create_directory(unpack_path / quiz_title) / "Scores.csv"
        quiz.to_csv(scores_path, index=False)


def fetch_submission_scores(quizzes: list[Quiz], quiz_path: Path, instance: Instance):
    scores = list()
    for quiz in quizzes:
        submissions = list(quiz.get_submissions())
        scores.append(get_submission_scores(submissions, quiz, instance))
    scores_data = concat(scores)
    scores_data.to_csv(quiz_path / "scores.csv.gz", index=False)
