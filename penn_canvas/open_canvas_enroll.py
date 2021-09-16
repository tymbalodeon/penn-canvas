from typer import echo

from .helpers import colorize, find_input, get_canvas, get_command_paths, process_input

COMMAND = "Open Canvas Enroll"
INPUT_FILE_NAME = "Open Canvas Users csv file"
REPORTS, RESULTS = get_command_paths(COMMAND)
HEADERS = ["Name", "Email"]
ACCOUNT = 1


def cleanup_data(data):
    data.drop_duplicates(subset=["Email"], inplace=True)
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


def create_or_delete_canvas_users(
    users, account_id, total, enroll=False, test=False, remove=False
):
    def create_or_delete_canvas_user(
        full_name, email, account_id, course_id, index, remove
    ):
        try:
            full_name = full_name.strip()
            email = email.strip()
            canvas = get_canvas("open_test" if test else "open", False)
            account = canvas.get_account(account_id)
            users = account.get_users(search_term=email)
            users_list = list()

            for user in users:
                users_list.append(user)

            if not remove and users_list:
                raise Exception("EMAIL ALREADY IN USE")
            elif remove and not users_list:
                raise Exception("USER NOT FOUND")

            if remove:
                account.delete_user(users_list[0])
                user = False
            else:
                pseudonym = {"unique_id": email}
                user_object = {"name": full_name}

                try:
                    user = account.create_user(pseudonym, user=user_object)
                except Exception:
                    raise Exception("EMAIL ALREADY IN USE")

            deleted = f"{colorize('DELETED', 'red')}"
            created = f"{colorize('CREATED', 'green')}"
            echo(
                f"- ({index + 1}/{total})"
                f" {deleted if remove else created}"
                " Canvas account for"
                f" {colorize(full_name, 'yellow')}{': ' if user else ''}"
                f"{colorize(user, 'magenta') if user else ''}."
            )

            if not remove and enroll and course_id:
                enroll_user_in_course(user, course_id, canvas)
        except Exception as error:
            colorize(
                f"- ({index + 1}/{total}) ERROR: Failed to"
                f" {'delete' if remove else 'create'} canvas user {full_name},"
                f" {email} ({error}).",
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

        create_or_delete_canvas_user(
            full_name, email, account_id, course_id, index, remove=remove
        )

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
    create_or_delete_canvas_users(users, ACCOUNT, TOTAL, test=test, remove=remove)
