from datetime import timedelta

from pandas import DataFrame
from tqdm import tqdm
from typer import echo

from .helpers import format_timedelta, format_timestamp, get_canvas, get_command_paths
from .style import color, print_item

COMMAND = "Integrity"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]


def parse_args(course, users, quizzes, test):
    canvas = get_canvas(test)
    course = canvas.get_course(course)
    users = [int(user) for user in users.split(" ")]
    quizzes = quizzes.split(" ")
    start = (
        start.strftime("%b %d, %Y (%I:%M:%S %p)")
        if (start := course.start_at_date)
        else ""
    )
    return course, users, quizzes, start


def get_user_data(
    course, quizzes, submissions, user, start, index, total, skip_page_views
):
    user_object = course.get_user(user)
    message = (
        f"Pulling data for {color(user_object, 'cyan', bold=True)}"
        f"{f' starting on {color(start)}' if start else ''}..."
    )
    print_item(index, total, message)
    submissions = [
        submission for submission in submissions if submission.user_id == user
    ]
    user_data = dict()
    for quiz_index, quiz in enumerate(quizzes):
        user_data[quiz.id] = [
            [
                str(user_object),
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
            ip_addresses = ", ".join(
                {
                    view.remote_ip
                    for view in (
                        tqdm(user_object.get_page_views(start_time=start))
                        if start
                        else tqdm(user_object.get_page_views())
                    )
                    if f"/quizzes/{quiz.id}" in view.url and view.participated
                }
            )
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
    result_path = RESULTS / f"{user_object}.csv"
    rows = list()
    for key in user_data.keys():
        rows = rows + user_data[key]
    user_data = DataFrame(rows, columns=columns)
    user_data.to_csv(result_path, index=False)


def integrity_main(course, users, quizzes, test, skip_page_views):
    course, users, quizzes, start = parse_args(course, users, quizzes, test)
    echo(f") Checking student activity in {color(course, 'blue', bold=True)}...")
    quizzes = [course.get_quiz(quiz) for quiz in quizzes]
    submissions = list()
    for quiz in quizzes:
        submissions = submissions + [
            submission
            for submission in quiz.get_submissions()
            if submission.user_id in users
        ]
    for index, user in enumerate(users):
        get_user_data(
            course,
            quizzes,
            submissions,
            user,
            start,
            index,
            len(users),
            skip_page_views,
        )
