from functools import lru_cache
from os import remove
from pathlib import Path
from tarfile import open as open_tarfile
from typing import Optional

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.quiz import Quiz
from canvasapi.submission import Submission
from pandas import DataFrame
from pandas.core.reshape.concat import concat
from pandas.core.series import Series
from pandas.io.parsers.readers import read_csv
from typer import echo

from penn_canvas.api import Instance
from penn_canvas.archive.assignments.assignment_descriptions import QUIZ_ID
from penn_canvas.archive.helpers import (
    COMPRESSION_TYPE,
    format_name,
    format_question_text,
    strip_tags,
)
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item


def get_assignment_submissions(assignment: Assignment) -> list[Submission]:
    include_parameters = ["submission_history", "user"]
    return list(assignment.get_submissions(include=include_parameters))


def get_question_text(question_id: int, quiz: Quiz) -> str:
    question = quiz.get_question(question_id)
    return format_question_text(question)


@lru_cache
def get_answer_text(answer_id: int, question_id: int, quiz: Quiz) -> str:
    question = quiz.get_question(question_id)
    answers = question.answers
    answer = next((answer for answer in answers if answer["id"] == answer_id), None)
    return answer["text"] if answer else ""


def get_answer_id(submission: dict):
    if "answer_id" in submission:
        return submission["answer_id"]
    else:
        return ""


def get_quiz_response(submission: dict, quiz: Quiz, user_name: str) -> list[str]:
    correct = submission["correct"]
    points = str(round(submission["points"], 2))
    points_possible = quiz.points_possible
    question_id = submission["question_id"]
    question = get_question_text(question_id, quiz)
    answer_id = get_answer_id(submission)
    answer = get_answer_text(answer_id, question_id, quiz) if answer_id else ""
    text = strip_tags(submission["text"])
    return [
        quiz.id,
        quiz.title,
        user_name,
        correct,
        points,
        points_possible,
        question,
        answer,
        text,
    ]


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
    verbose: bool,
) -> Series:
    total = len(submissions)
    responses = list()
    for index, submission in enumerate(submissions):
        histories = submission.submission_history
        user_name = submission.user["name"]
        if verbose:
            message = f"Getting submission data for {color(user_name, 'cyan')}..."
            print_item(index, total, message, prefix="\t*")
        for history in histories:
            submission_data = get_user_responses(history, quiz, user_name)
            columns = [
                "Quiz ID",
                "Quiz Title",
                "Student",
                "Correct",
                "Points",
                "Points Possible",
                "Question",
                "Answer",
                "Text",
            ]
            responses.append(DataFrame(submission_data, columns=columns))
    responses = concat(responses)
    return responses


def unpack_quiz_responses(
    compress_path: Path, archive_tar_path: Path, unpack_path: Path, verbose: bool
) -> Optional[Path]:
    echo("Unpacking quiz responses...")
    quizzes_tar_file = open_tarfile(archive_tar_path)
    quizzes_tar_file.extract(f"./responses.csv.{COMPRESSION_TYPE}", compress_path)
    unpacked_responses_path = compress_path / f"responses.csv.{COMPRESSION_TYPE}"
    responses = read_csv(unpacked_responses_path)
    responses.fillna("", inplace=True)
    quiz_ids = responses[QUIZ_ID].unique()
    quizzes = [responses[responses[QUIZ_ID] == quiz_id] for quiz_id in quiz_ids]
    total = len(quizzes)
    for index, quiz in enumerate(quizzes):
        quiz_title = next(iter(quiz["Quiz Title"].tolist()), "")
        quiz_title = format_name(quiz_title)
        if verbose:
            print_item(index, total, color(quiz_title))
        submissions_path = create_directory(unpack_path / quiz_title / "Submissions")
        user_names = quiz["Student"].unique()
        users = [quiz[quiz["Student"] == user_name] for user_name in user_names]
        total_users = len(users)
        for users_index, submissions in enumerate(users):
            user_name = next(iter(submissions["Student"].tolist()), "")
            if verbose:
                print_item(
                    users_index, total_users, color(user_name, "cyan"), prefix="\t*"
                )
            user_submissions_path = submissions_path / f"{user_name}.csv"
            submissions.to_csv(user_submissions_path, index=False)
    remove(compress_path / f"responses.csv.{COMPRESSION_TYPE}")
    return unpack_path


def fetch_quiz_responses(
    course: Course,
    quiz_path: Path,
    instance: Instance,
    verbose: bool,
):
    assignments = list(
        assignment
        for assignment in course.get_assignments()
        if assignment.is_quiz_assignment
    )
    responses = list()
    total = len(assignments)
    for index, assignment in enumerate(assignments):
        quiz = course.get_quiz(assignment.quiz_id, instance=instance)
        if verbose:
            print_item(index, total, color(quiz.title))
        submissions = get_assignment_submissions(assignment)
        responses.append(get_quiz_responses(submissions, quiz, verbose))
    response_data = concat(responses)
    response_data.to_csv(quiz_path / f"responses.csv.{COMPRESSION_TYPE}", index=False)
