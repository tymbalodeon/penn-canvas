from datetime import datetime

from pandas import read_csv
from typer import echo

from .helpers import (
    TODAY_AS_Y_M_D,
    colorize,
    find_input,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    process_input,
    toggle_progress_bar,
)

COMMAND = "Open Canvas Bulk Action"
INPUT_FILE_NAME = "Open Canvas Bulk Action csv file"
REPORTS, RESULTS, COMPLETED = get_command_paths(COMMAND, completed=True)
HEADERS = ["Name", "Email", "Canvas ID"]
ACCOUNT = 1


def cleanup_data(data):
    data.drop_duplicates(subset=["Email"], inplace=True)
    data = data.astype("string", errors="ignore")

    return data


def email_in_use(user, email):
    channels = [
        channel
        for channel in user.get_communication_channels()
        if channel.type == "email"
    ]
    email = [channel for channel in channels if channel.address == email]

    return bool(email)


def enroll_user_in_course(canvas, user, canvas_id, section):
    try:
        canvas_section = (
            canvas.get_section(canvas_id) if section else canvas.get_course(canvas_id)
        )
    except Exception:
        return "course not found", canvas_id

    try:
        enrollment = canvas_section.enroll_user(user)

        return "enrolled", enrollment
    except Exception:
        return "failed to enroll", canvas_section


def find_user_by_email(account, email):
    users = account.get_users(search_term=email)
    users = [
        user for user in users if user.login_id == email or email_in_use(user, email)
    ]

    return users


def create_user(account, full_name, email):
    user = find_user_by_email(account, email)

    if user:
        return "already in use", user[0]

    pseudonym = {"unique_id": email}
    user_object = {"name": full_name}

    try:
        canvas_user = account.create_user(pseudonym, user=user_object)

        return "created", canvas_user
    except Exception:
        return "already in use", None


def remove_user(account, email):
    user = find_user_by_email(account, email)

    if not user:
        return "not found"
    else:
        account.delete_user(user[0])

        return "deleted"


def enroll_user(canvas, email, canvas_id, section):
    users = find_user_by_email(canvas.get_account(ACCOUNT), email)
    status, course_or_enrollment = enroll_user_in_course(
        canvas, users[0], canvas_id, section
    )

    return status, course_or_enrollment


def process_result(result_path):
    result = read_csv(result_path)
    created = len(result[result["Status"] == "created"].index)
    deleted = len(result[result["Status"] == "deleted"].index)
    enrolled = len(result[result["Status"] == "enrolled"].index)
    failed_to_enroll = len(result[result["Status"] == "failed to enroll"].index)
    already_in_use = len(result[result["Status"] == "already in use"].index)
    course_not_found = len(result[result["Status"] == "course not found"].index)
    not_found = len(
        result[
            (result["Status"] != "created")
            & (result["Status"] != "deleted")
            & (result["Status"] != "enrolled")
            & (result["Status"] != "failed to enroll")
            & (result["Status"] != "already in use")
            & (result["Status"] != "course not found")
        ].index
    )

    result.drop(["index"], axis=1, inplace=True)
    result.sort_values("Status", inplace=True, ignore_index=True)
    result.to_csv(result_path, index=False)

    return (
        created,
        deleted,
        enrolled,
        failed_to_enroll,
        not_found,
        already_in_use,
        course_not_found,
    )


def print_messages(
    total,
    created,
    deleted,
    enrolled,
    failed_to_enroll,
    not_found,
    already_in_use,
    course_not_found,
):
    echo(
        f"- Processed {colorize(total, 'magenta')} {'user' if total == 1 else 'users'}."
    )

    if created:
        echo(
            "- Created"
            f" {colorize(created, 'green')} {'user' if created == 1 else 'users'}."
        )

    if deleted:
        echo(
            "- Deleted"
            f" {colorize(deleted, 'red')} {'user' if deleted == 1 else 'users'}."
        )

    if enrolled:
        echo(
            "- Enrolled"
            f" {colorize(enrolled, 'green')} {'user' if enrolled == 1 else 'users'}."
        )

    if failed_to_enroll:
        colorize(
            "- ERROR: Failed to enroll"
            f" {failed_to_enroll} {'user' if failed_to_enroll == 1 else 'users'}.",
            "red",
            True,
        )

    if not_found:
        colorize(
            "- ERROR: Failed to find"
            f" {not_found} {'user' if not_found == 1 else 'users'}.",
            "red",
            True,
        )

    if already_in_use:
        colorize(
            f"- ERROR: Found {already_in_use} user"
            f" {'account' if already_in_use == 1 else 'accounts'} already in use.",
            "red",
            True,
        )

    if course_not_found:
        colorize(
            f"- ERROR: Failed to find {course_not_found}"
            f" {'course' if course_not_found == 1 else 'courses'}.",
            "red",
            True,
        )


def open_canvas_bulk_action_main(verbose, force):
    def create_or_delete_canvas_user(user, canvas, verbose, args):
        account, action = args[:2]

        if action == "enroll":
            section = args[2]
            index, full_name, email, canvas_id = user[:-1]
        else:
            index, full_name, email = user[:-1]

        status = "deleted" if action == "remove" else "created"
        course = None
        error_message = False
        canvas_user = False

        try:
            full_name = full_name.strip()
            email = email.strip()

            if action == "enroll":
                try:
                    status, course = enroll_user(canvas, email, canvas_id, section)
                except Exception:
                    status, canvas_user = create_user(account, full_name, email)

                    if status == "created":
                        try:
                            status, course = enroll_user(
                                canvas, email, canvas_id, section
                            )
                        except Exception as error:
                            status = error
            elif action == "remove":
                status = remove_user(account, email)
            else:
                status, canvas_user = create_user(account, full_name, email)
        except Exception as error:
            status = error
            error_message = True

        users.at[index, ["Status"]] = status
        users.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose and error_message:
            colorize(
                f"- ({index + 1}/{TOTAL}) ERROR: Failed to"
                f" {'delete' if action == 'remove' else action} {full_name}"
                f" ({email}){f' in course {course}' if course else ''}: {status}.",
                "red",
                True,
            )
        elif verbose:
            echo(
                f"- ({index + 1}/{TOTAL})"
                f" {colorize(full_name, 'yellow')}{':' if canvas_user else ''}"
                f" {colorize(status.upper(), COLOR_MAP.get(status))}"
                f"{colorize(' ' + str(canvas_user), 'magenta') if canvas_user else ''}."
            )

    input_files, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS, date=False, open_canvas=True
    )

    RESULT_PATHS = list()

    for index, input_file in enumerate(input_files):
        if verbose:
            echo(f"==== FILE {index + 1}/{len(input_files)} ====")

        action = "create"
        display_action = "Creating"

        if "enroll" in input_file.stem.lower():
            action = "enroll"
            display_action = "Enrolling"
            section = False

            if "section" in input_file.stem.lower():
                section = True

        elif "remove" in input_file.stem.lower():
            action = "remove"
            display_action = "Removing"

        test = True if "test" in input_file.stem.lower() else False
        RESULT_STRING = f"{input_file.stem}_RESULT.csv"
        RESULT_PATH = RESULTS / RESULT_STRING
        START = get_start_index(force, RESULT_PATH)
        action_headers = HEADERS if action == "enroll" else HEADERS[:2]
        users, TOTAL = process_input(
            input_files,
            INPUT_FILE_NAME,
            REPORTS,
            please_add_message,
            action_headers,
            cleanup_data,
            missing_file_message,
            start=START,
        )
        users["Status"] = ""
        RESULT_HEADERS = action_headers + ["Status"]
        make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(RESULT_HEADERS))
        make_skip_message(START, "user")
        INSTANCE = "open_test" if test else "open"
        CANVAS = get_canvas(INSTANCE)

        echo(f") {display_action} {len(users)} users...")

        if verbose:
            COLOR_MAP = {
                "created": "green",
                "enrolled": "green",
                "deleted": "yellow",
                "failed to enroll": "red",
                "not found": "red",
                "already in use": "red",
                "course not found": "red",
            }
        ARGS = (
            (CANVAS.get_account(ACCOUNT), action, section)
            if action == "enroll"
            else (CANVAS.get_account(ACCOUNT), action)
        )
        toggle_progress_bar(users, create_or_delete_canvas_user, CANVAS, verbose, ARGS)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_path = RESULT_PATH.rename(RESULTS / f"{RESULT_PATH.stem}_{timestamp}.csv")
        RESULT_PATHS.append((new_path, TOTAL))
        input_file.rename(COMPLETED / input_file.name)

    colorize("SUMMARY:", "yellow", True)
    echo(f"- PROCESSED {colorize(len(RESULT_PATHS))} FILES.")

    for result_path, total in RESULT_PATHS:
        echo(f"==== {colorize(result_path.stem, 'green')} ====")
        (
            created,
            deleted,
            enrolled,
            failed_to_enroll,
            not_found,
            already_in_use,
            course_not_found,
        ) = process_result(result_path)
        print_messages(
            total,
            created,
            deleted,
            enrolled,
            failed_to_enroll,
            not_found,
            already_in_use,
            course_not_found,
        )

    colorize("FINISHED", "yellow", True)
