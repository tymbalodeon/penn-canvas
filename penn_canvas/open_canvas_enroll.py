from typer import echo

from .helpers import (
    TODAY_AS_Y_M_D,
    YEAR,
    find_input,
    colorize,
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
REPORTS, RESULTS = get_command_paths(COMMAND)
HEADERS = ["Full name", "Email address"]
ACCOUNT = 1


def cleanup_data(data):
    data.drop_duplicates(subset=["Email address"], inplace=True)
    data = data.astype("string", errors="ignore")

    return data


def enroll_user_in_course(user, course_id, canvas=None, test=False):
    try:
        if not canvas:
            canvas = get_canvas("open_test" if test else "open", False)

        course = canvas.get_course(course_id)
    except Exception:
        print(f"- FAILED to find course {course_id}.")

        return

    try:
        enrollment = course.enroll_user(user)

        print(f"- ENROLLED {user} in {course}: {enrollment}.")
    except Exception:
        print(f"- FAILED to enroll {user} in {course}.")


def create_canvas_users(users, account_id, total, enroll=False, test=False):
    def create_canvas_user(full_name, email, account_id, course_id, index):
        try:
            canvas = get_canvas("open_test" if test else "open", False)
            account = canvas.get_account(account_id)
            users = account.get_users(search_term=email)

            if users:
                raise Exception("EMAIL ALREADY IN USE")

            pseudonym = {"unique_id": email}
            user = {"name": full_name}
            account = canvas.get_account(account_id)
            user = account.create_user(pseudonym, user=user)

            echo(
                f"- ({index + 1}/{total}) CREATED Canvas account for"
                f" {colorize(full_name, 'yellow')}: {colorize(user, 'magenta')}."
            )

            if enroll and course_id:
                enroll_user_in_course(user, course_id, canvas)
        except Exception as error:
            colorize(
                f"- ({index + 1}/{total}) ERROR: Failed to create canvas user"
                f" {full_name}, {email} ({error}).",
                "red",
                True,
            )

    echo(f") Creating Canvas accounts for {len(users)} users...")

    for user in users.itertuples():
        if enroll:
            index, full_name, email, course_id = user
        else:
            index, full_name, email = user
            course_id = None

        create_canvas_user(full_name, email, account_id, course_id, index)

    echo("FINISHED")


def open_canvas_enroll_main(remove, test=False):
    input_files, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS, open_canvas=True, remove=remove
    )
    users, TOTAL = process_input(
        input_files,
        INPUT_FILE_NAME,
        REPORTS,
        please_add_message,
        HEADERS,
        cleanup_data,
        missing_file_message,
    )
    create_canvas_users(users, ACCOUNT, TOTAL, test=test)
