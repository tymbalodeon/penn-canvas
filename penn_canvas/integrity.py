from datetime import timedelta
from typing import Any

from canvasapi.course import Course
from canvasapi.quiz import Quiz
from canvasapi.submission import Submission
from canvasapi.user import User
from pandas import DataFrame
from typer import echo

from penn_canvas.api import Instance

from .api import get_course, validate_instance_name
from .helpers import format_timedelta, format_timestamp, get_command_paths
from .style import color, print_item

COMMAND_NAME = "Integrity"
RESULTS = get_command_paths(COMMAND_NAME)["results"]


def is_quiz_page_view(page_view, quiz_id):
    return f"/quizzes/{quiz_id}" in page_view.url and page_view.participated


def get_ip_addresses(user: User, quiz_id: str, start: str, end: str) -> str:
    if start and end:
        page_views_paginator = user.get_page_views(start_time=start, end_time=end)
    else:
        page_views_paginator = user.get_page_views()
    page_views = {
        page_view.remote_ip
        for page_view in page_views_paginator
        if is_quiz_page_view(page_view, quiz_id)
    }
    return ", ".join(page_views)


def get_user_data(
    course: Course,
    quizzes: list[Quiz],
    submissions: list[Submission],
    user_id: int,
    start: str,
    end: str,
    index: int,
    total: int,
    skip_page_views: bool,
):
    user = course.get_user(user_id)
    message = (
        f"Pulling data for {color(user, 'cyan', bold=True)}"
        f"{f' starting on {color(start)}' if start else ''}..."
    )
    print_item(index, total, message)
    submissions = [
        submission for submission in submissions if submission.user_id == user_id
    ]
    user_data = dict()
    for quiz_index, quiz in enumerate(quizzes):
        user_data[quiz.id] = [
            [
                str(user),
                str(quiz),
                format_timestamp(submission.started_at),
                format_timestamp(submission.finished_at),
                format_timedelta(timedelta(seconds=submission.time_spent)),
            ]
            for submission in submissions
            if submission.quiz_id == quiz.id
        ]
        if not skip_page_views:
            message = f"Pulling page views for {color(quiz, 'yellow')}..."
            print_item(quiz_index, len(quizzes), message)
            ip_addresses = get_ip_addresses(user, quiz.id, start, end)
            user_data[quiz.id] = [
                submission + [ip_addresses] for submission in user_data[quiz.id]
            ]
    columns = [
        "Student",
        "Quiz",
        "Started At",
        "Finished At",
        "Time Spent",
    ]
    if not skip_page_views:
        columns.append("IP Address")
    result_path = RESULTS / f"{user}.csv"
    rows: list[Any] = list()
    for key in user_data.keys():
        rows = rows + user_data[key]
    user_data_frame = DataFrame(rows, columns=columns)
    user_data_frame.to_csv(result_path, index=False)


def get_quiz_submissions_for_users(quiz: Quiz, user_ids: list[int]) -> list[Submission]:
    return [
        submission
        for submission in quiz.get_submissions()
        if submission.user_id in user_ids
    ]


def get_all_user_submissions_for_quizzes(
    quizzes: list[Quiz], user_ids: list[int]
) -> list[Submission]:
    submissions: list[Any] = list()
    for quiz in quizzes:
        submissions = submissions + get_quiz_submissions_for_users(quiz, user_ids)
    return submissions


def integrity_main(
    course_id: int,
    user_ids: list[int],
    quiz_ids: list[int],
    instance_name: str | Instance,
    skip_page_views: bool,
    start="",
    end="",
):
    instance = validate_instance_name(instance_name)
    course = get_course(course_id, instance=instance)
    echo(f") Checking student activity in {color(course, 'blue', bold=True)}...")
    quizzes = [course.get_quiz(quiz) for quiz in quiz_ids]
    submissions = get_all_user_submissions_for_quizzes(quizzes, user_ids)
    for index, user_id in enumerate(user_ids):
        get_user_data(
            course,
            quizzes,
            submissions,
            user_id,
            start,
            end,
            index,
            len(user_ids),
            skip_page_views,
        )
