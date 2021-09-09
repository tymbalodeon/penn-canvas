from canvasapi import CanvasException
from .helpers import (
    YEAR,
    find_input,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    process_input,
)

COMMAND = "Open Canvas Enroll"
INPUT_FILE_NAME = "Open Canvas Users csv file"
REPORTS, RESULTS, LOGS, PROCESSED = get_command_paths(COMMAND)
HEADERS = ["first name", "last name", "email"]
ACCOUNT = 96678


def cleanup_data(data):
    data.drop_duplicates(subset=["email"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")

    return data


def enroll_user_in_course(user, course_id, canvas=None):
    try:
        if not canvas:
            canvas = get_canvas()

        course = canvas.get_course(course_id)
    except Exception:
        print(f"- FAILED to find course {course_id}.")

        return

    try:
        enrollment = course.enroll_user(user)

        print(f"- ENROLLED {user} in {course}: {enrollment}.")
    except Exception:
        print(f"- FAILED to enroll {user} in {course}.")


def create_canvas_users(users, account_id, enroll=False):
    def create_canvas_user(email, full_name, account_id, course_id):
        pseudonym = {"unique_id": email}
        user = {"name": full_name}

        try:
            canvas = get_canvas()
            account = canvas.get_account(account_id)
            user = account.create_user(pseudonym, user=user)

            print(f"- CREATED Canvas account for {full_name}: {user}.")

            if enroll:
                enroll_user_in_course(user, course_id, canvas)
        except CanvasException as error:
            print(
                f"- ERROR: Failed to create canvas user {full_name}, {email} ({error})."
            )

    print(f") Creating Canvas accounts for {len(users)} users...")

    for user in users:
        email, full_name, course_id = user
        create_canvas_user(email, full_name, account_id, course_id)

    print("FINISHED")


def open_canvas_enroll_main(verbose, force):
    reports, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS
    )
    RESULT_PATH = RESULTS / f"{YEAR}_open_canvas_eroll_result.csv"
    START = get_start_index(force, RESULT_PATH, RESULTS)
    users, TOTAL = process_input(
        reports,
        INPUT_FILE_NAME,
        REPORTS,
        please_add_message,
        HEADERS,
        cleanup_data,
        missing_file_message,
        START,
    )
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(START, "user")
    CANVAS = get_canvas("open")
    create_canvas_users(users, ACCOUNT)
