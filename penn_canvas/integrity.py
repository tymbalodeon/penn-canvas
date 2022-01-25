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


def get_user_data(course, quizzes, submissions, user, start, index, total):
    user_object = course.get_user(user)
    submissions = [
        submission for submission in submissions if submission.user_id == user
    ]
    page_views_path = RESULTS / f"{user_object}_page_views.csv"
    submissions_path = RESULTS / f"{user_object}_submissions.csv"
    message = (
        f"Pulling page views for {color(user_object, 'cyan', bold=True)}"
        f"{f' starting on {color(start)}' if start else ''}..."
    )
    print_item(index, total, message)
    page_views = list()
    user_submissions = list()
    for index, quiz in enumerate(quizzes):
        message = f"Pulling page views for {color(quiz, 'yellow', bold=True)}..."
        print_item(index, len(quizzes), message)
        page_views = page_views + [
            [user_object, quiz, view]
            for view in (
                tqdm(user_object.get_page_views(start_time=start))
                if start
                else tqdm(user_object.get_page_views())
            )
            if f"/quizzes/{quiz.id}" in view.url
        ]
        user_submissions = user_submissions + [
            [user_object, quiz, submission]
            for submission in submissions
            if submission.quiz_id == quiz.id
        ]
    page_views = [
        [
            view[0],
            view[1],
            format_timestamp(view[2].created_at),
            view[2].participated,
            view[2].remote_ip,
            view[2].url,
            view[2].user_agent,
        ]
        for view in page_views
    ]
    user_submissions = [
        [
            submission[0],
            submission[1],
            format_timestamp(submission[2].started_at),
            format_timestamp(submission[2].finished_at),
            format_timedelta(timedelta(seconds=submission[2].time_spent)),
            submission[2].score,
            submission[2].quiz_points_possible,
        ]
        for submission in user_submissions
    ]
    page_view_columns = [
        "Student",
        "Quiz",
        "Created At",
        "Participated",
        "Remote IP",
        "URL",
        "User Agent",
    ]
    submission_columns = [
        "Student",
        "Quiz",
        "Started At",
        "Finished At",
        "Time Spent",
        "Score",
        "Quiz Points Possible",
    ]
    page_views = DataFrame(page_views, columns=page_view_columns)
    page_views.to_csv(page_views_path, index=False)
    user_submissions = DataFrame(user_submissions, columns=submission_columns)
    user_submissions.to_csv(submissions_path, index=False)


def integrity_main(course, users, quizzes, test):
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
        get_user_data(course, quizzes, submissions, user, start, index, len(users))
