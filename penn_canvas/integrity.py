from pandas import DataFrame
from tqdm import tqdm

from penn_canvas.helpers import format_timestamp, get_canvas, get_command_paths
from penn_canvas.style import print_item

COMMAND = "Integrity"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]


def integrity_main(course, users, quizzes, test):
    canvas = get_canvas(test)
    course = canvas.get_course(course)
    users = users.split(" ")
    quizzes = quizzes.split(" ")
    start = course.start_at_date if course.start_at_date else ""
    for index, user in enumerate(users):
        user_object = canvas.get_user(user)
        result_path = RESULTS / f"Student_Activity_User_{user_object}.csv"
        message = (
            f"Pulling page views for {user_object}"
            f"{f' starting on {start}' if start else ''}..."
        )
        print_item(index, len(users), message, ")")
        page_views = list()
        for index, quiz in enumerate(quizzes):
            quiz_object = course.get_quiz(quiz)
            message = f"Pulling page views for {quiz_object}..."
            print_item(index, len(quizzes), message, ")")
            page_views = page_views + [
                [quiz_object, view]
                for view in (
                    tqdm(user_object.get_page_views(start_time=start))
                    if start
                    else tqdm(user_object.get_page_views())
                )
                if f"/quizzes/{quiz}" in view.url
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
        columns = [
            "Quiz",
            "Created At",
            "Interaction Seconds",
            "Participated",
            "Remote IP",
            "URL",
            "User Agent",
        ]
        page_views = DataFrame(page_views, columns=columns)
        page_views.to_csv(result_path, index=False)
