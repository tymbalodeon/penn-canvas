from pandas import DataFrame
from tqdm import tqdm
from typer import echo

from .helpers import format_timestamp, get_canvas, get_command_paths
from .style import color, print_item

COMMAND = "Integrity"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]


def parse_args(course, users, quizzes, test):
    canvas = get_canvas(test)
    course = canvas.get_course(course)
    users = [int(user) for user in users.split(" ")]
    quizzes = quizzes.split(" ")
    start = course.start_at_date if course.start_at_date else ""
    return course, users, quizzes, start


def get_user_data(course, quizzes, user, start, index, total):
    user_object = course.get_user(user)
    page_views_path = RESULTS / f"{user_object}_page_views.csv"
    submissions_path = RESULTS / f"{user_object}_submission.csv"
    message = (
        f"Pulling page views for {user_object}"
        f"{f' starting on {start}' if start else ''}..."
    )
    print_item(index, total, message, ")")
    page_views = list()
    for index, quiz in enumerate(quizzes):
        message = f"Pulling page views for {quiz}..."
        print_item(index, len(quizzes), message, ")")
        page_views = page_views + [
            [quiz, view]
            for view in (
                tqdm(user_object.get_page_views(start_time=start))
                if start
                else tqdm(user_object.get_page_views())
            )
            if f"/quizzes/{quiz.id}" in view.url
        ]
    page_views = [
        [
            view[0],
            format_timestamp(view[1].created_at),
            view[1].interaction_seconds,
            view[1].participated,
            view[1].remote_ip,
            view[1].url,
            view[1].user_agent,
        ]
        for view in page_views
    ]
    page_view_columns = [
        "Quiz",
        "Created At",
        "Interaction Seconds",
        "Participated",
        "Remote IP",
        "URL",
        "User Agent",
    ]
    submission_columns = [
        "Attempt",
        "Attempts Left",
        "End At",
        "Excused?",
        "Extra Attempts",
        "Extra Time",
        "Finished At",
        "Fudge Points",
        "Has Seen Results",
        "Kept Score",
        "Manually Unlocked",
        "Overdue And Needs Submission",
        "Quiz Points Possible",
        "Quiz Version",
        "Score",
        "Score Before Regrade",
        "Started At",
        "Time Spent",
        "Workflow State",
    ]
    page_views = DataFrame(page_views, columns=page_view_columns)
    page_views.to_csv(page_views_path, index=False)


def integrity_main(course, users, quizzes, test):
    course, users, quizzes, start = parse_args(course, users, quizzes, test)
    echo(f") Checking student activity in {color(course, 'blue', bold=True)}...")
    quizzes = [
        {
            "quiz": (quiz_object := course.get_quiz(quiz)),
            "submissions": [
                submission
                for submission in quiz_object.get_submissions()
                if submission.user_id in users
            ],
        }
        for quiz in quizzes
    ]
    for index, user in enumerate(users):
        get_user_data(course, quizzes, user, start, index, len(users))
