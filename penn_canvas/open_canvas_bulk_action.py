from datetime import datetime
from pathlib import Path

from pandas import concat, read_csv
from typer import echo

from penn_canvas.browser import browser_main

from .helpers import (
    color,
    confirm_global_protect_enabled,
    find_input,
    get_canvas,
    get_command_paths,
    get_data_warehouse_cursor,
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
HEADERS = ["Name", "Email", "Course ID", "Section ID", "Notify"]
ACCOUNT = 1
UNENROLL_TASKS = {"conclude", "delete", "deactivate", "inactivate"}
ENROLLMENT_TYPES = {
    "student": "StudentEnrollment",
    "teacher": "TeacherEnrollment",
    "ta": "TaEnrollment",
    "observer": "ObserverEnrollment",
    "designer": "DesignerEnrollment",
}
COURSES_CACHE: dict[int, dict] = {}


def cleanup_data(data, action):
    subset = "Pennkey" if action == "penn_id" else "Email"
    data.drop_duplicates(subset=[subset], inplace=True)
    return data.astype("string", errors="ignore")


def get_timestamped_path(result_path, open_test):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_path_stem = f"{'TEST_' if open_test else ''}{result_path.stem}_{timestamp}.csv"
    new_path = RESULTS / new_path_stem
    if result_path.is_file():
        result_path.rename(new_path)
    else:
        Path.touch(new_path)
    return new_path


def get_enrollment_type(enrollment_type):
    try:
        return ENROLLMENT_TYPES[enrollment_type.lower()]
    except Exception:
        return None


def get_enrollment_id(course_id, section_id):
    try:
        return int(section_id), True
    except Exception:
        return course_id, False


def get_penn_id_from_penn_key(penn_key):
    cursor = get_data_warehouse_cursor()
    cursor.execute(
        """
        SELECT
            penn_id
        FROM
            person_all_v
        WHERE
            pennkey = :pennkey
        """,
        pennkey=penn_key.strip().lower(),
    )
    for penn_id in cursor:
        return penn_id[0]


def email_in_use(user, email):
    channels = [
        channel
        for channel in user.get_communication_channels()
        if channel.type == "email"
    ]
    return bool([channel for channel in channels if channel.address == email])


def find_user_by_email(account, email):
    users = [
        user
        for user in account.get_users(search_term=email)
        if user.login_id.lower() == email.lower() or email_in_use(user, email)
    ]
    return next(iter(users), None)


def create_user(account, full_name, email):
    user = find_user_by_email(account, email)
    if user:
        return "already in use", user
    pseudonym = {"unique_id": email}
    user_object = {"name": full_name}
    try:
        canvas_user = account.create_user(pseudonym, user=user_object)
        return "created", canvas_user
    except Exception:
        return "already in use", None


def update_user_name(account, new_name, email):
    user = find_user_by_email(account, email)
    if not user:
        return "not found"
    else:
        user.edit(user={"name": new_name})
        return "updated"


def remove_user(account, email):
    user = find_user_by_email(account, email)
    if not user:
        return "not found"
    else:
        account.delete_user(user)
        return "removed"


def get_canvas_section_or_course(canvas, canvas_id, section):
    if canvas_id in COURSES_CACHE and "section" in COURSES_CACHE[canvas_id]:
        return COURSES_CACHE[canvas_id]["section"]
    else:
        try:
            canvas_section = (
                canvas.get_section(canvas_id)
                if section
                else canvas.get_course(canvas_id)
            )
        except Exception:
            canvas_section = "course not found"
        COURSES_CACHE[canvas_id] = dict()
        COURSES_CACHE[canvas_id]["section"] = canvas_section
        return canvas_section


def get_enrollment_login(canvas, enrollment):
    user = canvas.get_user(enrollment.user["id"])
    return {
        "enrollment": enrollment,
        "login_id": user.login_id.lower() if user.login_id else "",
        "email": user.email.lower() if user.email else "",
    }


def get_enrollments(canvas, canvas_id, canvas_section):
    if canvas_id in COURSES_CACHE and "enrollments" in COURSES_CACHE[canvas_id]:
        return COURSES_CACHE[canvas_id]["enrollments"]
    else:
        try:
            enrollments = [
                enrollment for enrollment in canvas_section.get_enrollments()
            ]
            enrollments = [
                get_enrollment_login(canvas, enrollment) for enrollment in enrollments
            ]
        except Exception:
            enrollments = []
        COURSES_CACHE[canvas_id]["enrollments"] = enrollments
        return enrollments


def get_enrollment_by_email(email, enrollments):
    email = email.lower()
    return next(
        (
            enrollment
            for enrollment in enrollments
            if enrollment["login_id"].lower() == email
            or enrollment["email"].lower() == email
        ),
        None,
    )


def enroll_user(
    canvas, account, full_name, email, enrollment_type, canvas_id, section, notify
):
    user = find_user_by_email(account, email)
    if not user:
        user = create_user(account, full_name, email)[1]
    canvas_section = get_canvas_section_or_course(canvas, canvas_id, section)
    if canvas_section == "course not found":
        return canvas_section, canvas_id, ""
    if not enrollment_type:
        return "invalid enrollment type", canvas_section, ""
    try:
        enrollment = canvas_section.enroll_user(
            user, enrollment={"notify": notify, "type": enrollment_type}
        )
        return "enrolled", enrollment, ""
    except Exception as error:
        return "failed to enroll", canvas_section, str(error)


def unenroll_user(canvas, email, canvas_id, section, task="conclude"):
    task = task.lower() if task in UNENROLL_TASKS else "conclude"
    canvas_section = get_canvas_section_or_course(canvas, canvas_id, section)
    if not canvas_section or canvas_section == "course not found":
        return canvas_section, canvas_id
    try:
        enrollments = get_enrollments(canvas, canvas_id, canvas_section)
        enrollment = get_enrollment_by_email(email, enrollments)
    except Exception:
        enrollment = None
    if not enrollment:
        return "enrollment not found", canvas_section
    else:
        try:
            unenrollment = enrollment["enrollment"].deactivate(task)
            return "unenrolled", unenrollment
        except Exception:
            return "failed to unenroll", enrollment


def process_result(result_path):
    result = read_csv(result_path)
    penn_id = "penn_id" in str(result_path)
    if penn_id:
        penn_ids = result[result["Penn ID"].astype(str).str.isnumeric()]
        not_found = result[result["Penn ID"] == "not found"]
        error = result[result["Penn ID"].astype(str).str.contains("ERROR", regex=False)]
        result = concat([error, not_found, penn_ids])
        counts = (
            len(penn_ids.index),
            len(not_found.index),
            len(error.index),
        )
    else:
        created = result[result["Status"] == "created"]
        removed = result[result["Status"] == "removed"]
        enrolled = result[result["Status"] == "enrolled"]
        unenrolled = result[result["Status"] == "unenrolled"]
        failed_to_enroll = result[result["Status"] == "failed to enroll"]
        failed_to_unenroll = result[result["Status"] == "failed to unenroll"]
        already_in_use = result[result["Status"] == "already in use"]
        course_not_found = result[result["Status"] == "course not found"]
        enrollment_not_found = result[result["Status"] == "enrollment not found"]
        missing_value = result[result["Status"] == "missing value"]
        invalid_enrollment_type = result[result["Status"] == "invalid enrollment type"]
        error = result[
            (result["Status"] != "created")
            & (result["Status"] != "removed")
            & (result["Status"] != "enrolled")
            & (result["Status"] != "unenrolled")
            & (result["Status"] != "failed to enroll")
            & (result["Status"] != "failed to unenroll")
            & (result["Status"] != "already in use")
            & (result["Status"] != "course not found")
            & (result["Status"] != "enrollment not found")
            & (result["Status"] != "missing value")
            & (result["Status"] != "invalid enrollment type")
        ]
        result = concat(
            [
                invalid_enrollment_type,
                missing_value,
                course_not_found,
                enrollment_not_found,
                failed_to_enroll,
                failed_to_unenroll,
                error,
                already_in_use,
                enrolled,
                unenrolled,
                created,
                removed,
            ]
        )
        counts = (
            len(created.index),
            len(removed.index),
            len(enrolled.index),
            len(unenrolled.index),
            len(failed_to_enroll.index),
            len(failed_to_unenroll.index),
            len(error.index),
            len(already_in_use.index),
            len(course_not_found.index),
            len(enrollment_not_found.index),
            len(missing_value.index),
            len(invalid_enrollment_type.index),
        )
    result.drop(["index"], axis=1, inplace=True)
    file_name = result_path.stem.lower()
    if (
        "enroll" in file_name
        and "unenroll" not in file_name
        and result["Error"].isna().all()
    ):
        result.drop(["Error"], axis=1, inplace=True)
    result.to_csv(result_path, index=False)
    return counts, penn_id


def print_messages(total, counts, penn_id):
    echo(f"- Processed {color(total, 'magenta')} {'user' if total == 1 else 'users'}.")
    if penn_id:
        penn_ids, not_found, error = counts
        if penn_ids:
            echo(
                "- Found Penn IDs for"
                f" {color(penn_ids, 'green')} {'user' if penn_ids == 1 else 'users'}."
            )
        if not_found:
            color(
                "- ERROR: Failed to find"
                f" {not_found} {'user' if not_found == 1 else 'users'}.",
                "red",
                True,
            )
        if error:
            color(
                "- ERROR: Encountered an error for"
                f" {error} {'user' if error == 1 else 'users'}.",
                "red",
                True,
            )
    else:
        (
            created,
            removed,
            enrolled,
            unenrolled,
            failed_to_enroll,
            failed_to_unenroll,
            not_found,
            already_in_use,
            course_not_found,
            enrollment_not_found,
            missing_value,
            invalid_enrollment_type,
        ) = counts
        if created:
            echo(
                "- Created"
                f" {color(created, 'green')} {'user' if created == 1 else 'users'}."
            )
        if removed:
            echo(
                "- Removed"
                f" {color(removed, 'red')} {'user' if removed == 1 else 'users'}."
            )
        if enrolled:
            echo(
                "- Enrolled"
                f" {color(enrolled, 'green')} {'user' if enrolled == 1 else 'users'}."
            )
        if unenrolled:
            echo(
                "- Unenrolled"
                f" {color(unenrolled, 'green')} "
                f"{'user' if unenrolled == 1 else 'users'}."
            )
        if failed_to_enroll:
            color(
                "- ERROR: Failed to enroll"
                f" {failed_to_enroll} {'user' if failed_to_enroll == 1 else 'users'}.",
                "red",
                True,
            )
        if failed_to_unenroll:
            color(
                "- ERROR: Failed to unenroll"
                f" {failed_to_unenroll} "
                f"{'user' if failed_to_unenroll == 1 else 'users'}.",
                "red",
                True,
            )
        if not_found:
            color(
                "- ERROR: Failed to find"
                f" {not_found} {'user' if not_found == 1 else 'users'}.",
                "red",
                True,
            )
        if already_in_use:
            color(
                f"- ERROR: Found {already_in_use} user"
                f" {'account' if already_in_use == 1 else 'accounts'} already in use.",
                "red",
                True,
            )
        if course_not_found:
            color(
                f"- ERROR: Failed to find {course_not_found}"
                f" {'course' if course_not_found == 1 else 'courses'}.",
                "red",
                True,
            )
        if enrollment_not_found:
            color(
                f"- ERROR: Failed to find {enrollment_not_found}"
                f" {'enrollment' if enrollment_not_found == 1 else 'enrollments'}.",
                "red",
                True,
            )
        if missing_value:
            color(
                "- ERROR: Found"
                f" {missing_value} {'field' if missing_value == 1 else 'fields'} with"
                " missing values",
                "red",
                True,
            )
        if invalid_enrollment_type:
            color(
                "- ERROR: Found"
                f" {invalid_enrollment_type} {'user' if missing_value == 1 else 'users'} with"
                " invalid enrollment types",
                "red",
                True,
            )


def open_canvas_bulk_action_main(verbose, force, test):
    def perform_canvas_action(user, canvas, verbose, args):
        account, action = args
        full_name = ""
        email = ""
        enrollment_type = ""
        course_id = ""
        section_id = ""
        canvas_id = ""
        notify = ""
        task = ""
        penn_key = ""
        section = None
        if action == "enroll":
            (
                index,
                full_name,
                email,
                enrollment_type,
                course_id,
                section_id,
                notify,
            ) = user[:-2]
            notify = bool("true" in notify.lower())
            canvas_id, section = get_enrollment_id(course_id, section_id)
            enrollment_type = get_enrollment_type(enrollment_type)
        elif action == "unenroll":
            index, full_name, email, course_id, section_id, task = user[:-1]
            canvas_id, section = get_enrollment_id(course_id, section_id)
        elif action == "penn_id":
            index, full_name, penn_key = user[:-1]
        elif action == "user_agent":
            index, course_id = user
        else:
            index, full_name, email = user[:-1]
        status = "removed" if action == "remove" else "created"
        course = None
        error_message = False
        enroll_error = ""
        canvas_user = False
        try:
            for user in [full_name, email, penn_key]:
                if not isinstance(user, str):
                    raise Exception("missing value")
            if action in {"enroll", "unenroll"} and not section:
                try:
                    int(course_id)
                except Exception:
                    raise Exception("missing value")
            if full_name:
                full_name = " ".join(full_name.strip().split())
            if email:
                email = email.strip()
            if action == "unenroll":
                status, course = unenroll_user(canvas, email, canvas_id, section, task)
            elif action == "enroll":
                status, course, enroll_error = enroll_user(
                    canvas,
                    account,
                    full_name,
                    email,
                    enrollment_type,
                    canvas_id,
                    section,
                    notify,
                )
            elif action == "remove":
                status = remove_user(account, email)
            elif action == "update":
                status = update_user_name(account, full_name, email)
            elif action == "penn_id":
                status = get_penn_id_from_penn_key(penn_key) or "not found"
            elif not action == "user_agent":
                status, canvas_user = create_user(account, full_name, email)
        except Exception as error_status:
            status = f"ERROR: {str(error_status)}"
            error_message = True
        if action == "penn_id":
            users.at[index, ["Penn ID"]] = status
        else:
            users.at[index, ["Status"]] = status
        if enroll_error:
            users.at[index, ["Error"]] = enroll_error
        users.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)
        if verbose and error_message:
            color(
                f"- ({index + 1}/{TOTAL}) ERROR: Failed to"
                f" {'get Penn ID for' if action == 'penn_id' else action} {full_name}"
                f" ({email}){f' in course {course}' if course else ''}: {status}.",
                "red",
                True,
            )
        elif verbose:
            if action == "penn_id":
                if error_message:
                    display_color = "red"
                else:
                    display_color = "green" if status != "not found" else "yellow"
            else:
                display_color = COLOR_MAP.get(status)
            echo(
                f"- ({index + 1}/{TOTAL})"
                f" {color(full_name, 'yellow')}{':' if canvas_user else ''}"
                f" {color(status.upper(), display_color)}"
                f"{color(' ' + str(canvas_user), 'magenta') if canvas_user else ''}."
            )

    user_agent_courses = ""
    input_files, missing_file_message = find_input(
        INPUT_FILE_NAME, REPORTS, date=False, open_canvas=True
    )
    RESULT_PATHS = list()
    input_files.sort(reverse=True)
    for index, input_file in enumerate(input_files):
        action = "create"
        display_action = "Creating"
        file_name = input_file.stem.lower()
        if "unenroll" in file_name:
            action = "unenroll"
            display_action = "Unenrolling"
        elif "enroll" in file_name:
            action = "enroll"
            display_action = "Enrolling"
        elif "remove" in file_name:
            action = "remove"
            display_action = "Removing"
        elif "update" in file_name:
            action = "update"
            display_action = "Updating"
        elif "penn_id" in file_name:
            if not confirm_global_protect_enabled():
                continue
            action = "penn_id"
            display_action = "Getting Penn IDs for"
        elif "user_agent" in file_name:
            action = "user_agent"
            display_action = "Getting user agent information for"
        open_test = test or "test" in file_name
        RESULT_STRING = f"{input_file.stem}_RESULT.csv"
        RESULT_PATH = RESULTS / RESULT_STRING
        START = get_start_index(force, RESULT_PATH)
        INSTANCE = "open_test" if open_test else "open"
        if action == "enroll":
            action_headers = HEADERS[:]
            action_headers.insert(2, "Type")
        elif action == "unenroll":
            action_headers = HEADERS[:-1] + ["Task"]
        elif action == "penn_id":
            action_headers = HEADERS[:1] + ["Pennkey"]
        else:
            action_headers = HEADERS[:2]
        if action == "user_agent":
            courses = read_csv(input_file)["Course ID"].tolist()
            user_agent_courses = len(courses)
            for course in courses:
                new_path = get_timestamped_path(RESULT_PATH, open_test)
                new_path = new_path.rename(
                    RESULTS / f"{new_path.stem}_COURSE_{course}.csv"
                )
                browser_main([course], INSTANCE, new_path)
                new_path.rename(RESULTS / f"{new_path.stem}_COMPLETED.csv")
            RESULT_PATHS.append((input_file, None))
            input_file.rename(COMPLETED / input_file.name)
        else:
            users, TOTAL, dated_input_file = process_input(
                input_files,
                INPUT_FILE_NAME,
                REPORTS,
                action_headers,
                cleanup_data,
                missing_file_message,
                args=action,
                start=START,
                open_canvas=True,
            )
            if action == "penn_id":
                users["Penn ID"] = ""
                RESULT_HEADERS = action_headers + ["Penn ID"]
            elif action == "user_agent":
                RESULT_HEADERS = ["Canvas User ID", "Name", "Email"]
                users[RESULT_HEADERS] = ""
            else:
                users["Status"] = ""
                RESULT_HEADERS = action_headers + ["Status"]
                if action == "enroll":
                    users["Error"] = ""
                    RESULT_HEADERS = RESULT_HEADERS + ["Error"]
            make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(RESULT_HEADERS))
            make_skip_message(START, "user")
            CANVAS = get_canvas(INSTANCE) if action != "penn_id" else None
            echo(
                f") {display_action} {len(users)} "
                f"user{'s' if len(users) > 1 else ''}..."
            )
            if verbose:
                COLOR_MAP = {
                    "created": "green",
                    "enrolled": "green",
                    "unenrolled": "green",
                    "removed": "yellow",
                    "failed to enroll": "red",
                    "failed to unenroll": "red",
                    "not found": "red",
                    "enrollment not found": "red",
                    "failed to unenroll": "red",
                    "already in use": "red",
                    "course not found": "red",
                }
            ARGS = (CANVAS.get_account(ACCOUNT) if CANVAS else CANVAS, action)
            if verbose:
                echo(f"==== FILE {index + 1}/{len(input_files)} ====")
                color(input_file.stem, "blue", True)
            toggle_progress_bar(users, perform_canvas_action, CANVAS, verbose, ARGS)
            new_path = get_timestamped_path(RESULT_PATH, open_test)
            RESULT_PATHS.append((new_path, TOTAL))
            dated_input_file.rename(COMPLETED / dated_input_file.name)
    color("SUMMARY:", "yellow", True)
    echo(f"- PROCESSED {color(len(RESULT_PATHS))} FILES.")
    for result_path, total in RESULT_PATHS:
        echo(f"==== {color(result_path.stem, 'green')} ====")
        if total is None:
            echo(
                "- Processed"
                f" {color(user_agent_courses)} "
                f"{'course' if user_agent_courses == 1 else 'courses'}"
            )
        else:
            counts, penn_id = process_result(result_path)
            print_messages(total, counts, penn_id)
    color("FINISHED", "yellow", True)
