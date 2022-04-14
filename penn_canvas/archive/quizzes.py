from functools import lru_cache
from pathlib import Path
from shutil import make_archive, rmtree
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.quiz import Quiz, QuizQuestion
from canvasapi.submission import Submission
from pandas import DataFrame, read_csv
from pandas.core.reshape.concat import concat
from typer import echo, progressbar

from penn_canvas.api import Instance, get_user
from penn_canvas.archive.assignments.assignments import ASSIGNMENTS_TAR_NAME
from penn_canvas.archive.assignments.descriptions import (
    ASSIGNMENT_ID,
    ASSIGNMENT_NAME,
    DESCRIPTIONS_COMPRESSED_FILE,
    QUIZ_ASSIGNMENT,
)
from penn_canvas.archive.helpers import TAR_COMPRESSION_TYPE, TAR_EXTENSION
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item

from .helpers import format_text, print_description, strip_tags

QUIZ_ID = "Quiz ID"
QUIZ_TITLE = "Quiz Title"
QUIZZES_TAR_STEM = "quizzes"
UNPACK_QUIZZES_DIRECTORY = QUIZZES_TAR_STEM.title()
QUIZZES_TAR_NAME = f"{QUIZZES_TAR_STEM}.{TAR_EXTENSION}"


def format_question_text(question: QuizQuestion) -> str:
    return strip_tags(question.question_text)


def get_question_answers(question: QuizQuestion) -> str:
    return " / ".join([answer["text"] for answer in question.answers])


def get_questions_and_answers(quiz: Quiz) -> DataFrame:
    questions = list(quiz.get_questions())
    questions = [
        [format_question_text(question), get_question_answers(question)]
        for question in questions
    ]
    return DataFrame(questions, columns=["Question", "Answers"])


def get_quiz_questions(quiz: Quiz, quiz_path: Path):
    questions = get_questions_and_answers(quiz)
    questions_path = quiz_path / f"{quiz.title}_QUESTIONS.csv"
    questions.to_csv(questions_path, index=False)


def get_quiz_assignment(quiz: Quiz, course: Course) -> Optional[Assignment]:
    if not quiz.assignment_id:
        return None
    return course.get_assignment(quiz.assignment_id)


def get_assignment_submissions(assignment: Assignment) -> list[Submission]:
    include_parameters = ["submission_history", "user"]
    return list(assignment.get_submissions(include=include_parameters))


@lru_cache
def get_question_text(question_id: int, quiz: Quiz) -> str:
    question = quiz.get_question(question_id)
    return format_question_text(question)


def get_quiz_response(submission: dict, quiz: Quiz, name: str) -> list[str]:
    correct = submission["correct"]
    points = str(round(submission["points"], 2))
    points_possible = quiz.points_possible
    question_id = submission["question_id"]
    question = get_question_text(question_id, quiz)
    text = strip_tags(submission["text"])
    return [name, correct, points, points_possible, question, text]


def get_user_responses(history: dict, quiz: Quiz, name: str):
    if "submission_data" not in history:
        return []
    return [
        get_quiz_response(submission, quiz, name)
        for submission in history["submission_data"]
    ]


def get_quiz_responses(
    submissions: list[Submission],
    quiz: Quiz,
    quiz_path: Path,
    verbose: bool,
):
    total = len(submissions)
    for index, submission in enumerate(submissions):
        histories = submission.submission_history
        user_name = submission.user["name"]
        if verbose:
            message = f"Getting submission data for {color(user_name, 'cyan')}..."
            print_item(index, total, message, prefix="\t*")
        for history in histories:
            submission_data = get_user_responses(history, quiz, user_name)
            columns = [
                "Student",
                "Correct",
                "Points",
                "Points Possible",
                "Question",
                "Text",
            ]
            history_data_frame = DataFrame(submission_data, columns=columns)
            file_name = f"{user_name}_submissions_{history['id']}.csv"
            submissions_path = create_directory(quiz_path / "Submissions")
            submission_data_path = submissions_path / file_name
            history_data_frame.to_csv(submission_data_path, index=False)


def get_submission_score(
    submission: Submission, points_possible: str, instance: Instance
):
    name = get_user(submission.user_id, instance=instance).name
    score = str(round(submission.score, 2)) if submission.score else ""
    return [name, score, points_possible]


def get_submission_scores(
    submissions: list[Submission], quiz: Quiz, quiz_path: Path, instance: Instance
):
    points_possible = quiz.points_possible
    submission_scores = [
        get_submission_score(submission, points_possible, instance)
        for submission in submissions
    ]
    columns = ["Student", "Score", "Points Possible"]
    user_scores = DataFrame(submission_scores, columns=columns)
    scores_path = quiz_path / f"{quiz.title}_SCORES.csv"
    user_scores.to_csv(scores_path, index=False)


def unpack_quizzes(compress_path: Path, unpack_path: Path, verbose: bool):
    echo(f"{compress_path}, {unpack_path}, {verbose}")


def get_quiz(
    course: Course,
    quiz: Quiz,
    compress_path: Path,
    instance: Instance,
    verbose: bool,
    index=0,
    total=0,
):
    if verbose:
        print_item(index, total, color(quiz.title))
    quiz_path = create_directory(compress_path / "Quizzes")
    get_quiz_questions(quiz, quiz_path)
    submissions = list(quiz.get_submissions())
    get_submission_scores(submissions, quiz, quiz_path, instance)
    assignment = get_quiz_assignment(quiz, course)
    if assignment:
        submissions = get_assignment_submissions(assignment)
        get_quiz_responses(submissions, quiz, quiz_path, verbose)


def get_description(quiz: Quiz, verbose: bool, index: int, total: int):
    description = format_text(quiz.description)
    title = quiz.title
    if verbose:
        print_description(index, total, title, description)
    return [quiz.id, title, description]


def get_descriptions(compress_path: Path, quizzes: list[Quiz], verbose: bool):
    assignments_tar_path = compress_path / ASSIGNMENTS_TAR_NAME
    descriptions_path = compress_path / DESCRIPTIONS_COMPRESSED_FILE
    fetched_descriptions = list()
    descriptions = DataFrame()
    if assignments_tar_path.exists():
        assignments_tar_file = open_tarfile(assignments_tar_path)
        assignments_tar_file.extract(f"./{DESCRIPTIONS_COMPRESSED_FILE}", compress_path)
        descriptions = read_csv(descriptions_path, dtype={QUIZ_ID: str})
        descriptions = descriptions[descriptions[QUIZ_ASSIGNMENT] == True]  # noqa
        descriptions = descriptions.reset_index(drop=True)
        descriptions = descriptions.drop(
            [ASSIGNMENT_ID, QUIZ_ASSIGNMENT], axis="columns"
        )
        descriptions = descriptions.rename(columns={ASSIGNMENT_NAME: QUIZ_TITLE})
        fetched_descriptions = descriptions[QUIZ_ID].tolist()
    fetched_descriptions_count = len(fetched_descriptions)
    if verbose and fetched_descriptions_count:
        count = color(fetched_descriptions_count, "cyan")
        echo(f"Skipping {count} descriptions previously fetched from assignments...")
    quizzes = [quiz for quiz in quizzes if str(quiz.id) not in fetched_descriptions]
    total = len(quizzes)
    quiz_descriptions = [
        get_description(quiz, verbose, index, total)
        for index, quiz in enumerate(quizzes)
    ]
    columns = [QUIZ_ID, QUIZ_TITLE, "Description"]
    quiz_descriptions_data_frame = DataFrame(quiz_descriptions, columns=columns)
    descriptions = concat([descriptions, quiz_descriptions_data_frame])
    descriptions.to_csv(descriptions_path, index=False)


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
    total = len(quizzes)
    get_descriptions(compress_path, quizzes, verbose)
    if verbose:
        for index, quiz in enumerate(quizzes):
            get_quiz(course, quiz, compress_path, instance, verbose, index, total)
    else:
        with progressbar(quizzes, length=total) as progress:
            for quiz in progress:
                get_quiz(course, quiz, compress_path, instance, verbose)
    quizzes_directory = str(quizzes_path)
    make_archive(quizzes_directory, TAR_COMPRESSION_TYPE, root_dir=quizzes_directory)
    rmtree(quizzes_path)
