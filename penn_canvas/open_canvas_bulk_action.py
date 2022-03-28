from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from canvasapi.account import Account
from canvasapi.course import Course
from canvasapi.enrollment import Enrollment
from canvasapi.section import Section
from canvasapi.user import User
from click.termui import progressbar
from pandas import concat, read_csv
from pandas.core.frame import DataFrame
from pandas.core.series import Series
from typer import echo

from penn_canvas.browser import browser_main
from penn_canvas.style import print_item

from .api import (
    Instance,
    get_account,
    get_course,
    get_data_warehouse_cursor,
    get_main_account_id,
    get_section,
    get_user,
)
from .helpers import (
    BASE_PATH,
    color,
    confirm_global_protect_enabled,
    create_directory,
    find_input,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    make_list,
    print_skip_message,
    process_input,
    switch_logger_file,
)

INPUT_FILE_NAME = "Open Canvas Bulk Action csv file"
COMMAND_PATH = create_directory(BASE_PATH / "Open Canvas Bulk Action")
INPUT = create_directory(COMMAND_PATH / "Input")
RESULTS = create_directory(COMMAND_PATH / "RESULTS")
COMPLETED = create_directory(COMMAND_PATH / "Completed")
LOGS = create_directory(COMMAND_PATH / "Logs")
HEADERS = ["Name", "Email", "Course ID", "Section ID", "Notify"]
UNENROLL_TASKS = {"conclude", "delete", "deactivate", "inactivate"}
ENROLLMENT_TYPES = {
    "student": "StudentEnrollment",
    "teacher": "TeacherEnrollment",
    "ta": "TaEnrollment",
    "observer": "ObserverEnrollment",
    "designer": "DesignerEnrollment",
}


class Action(Enum):
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    ENROLL = "enroll"
    UNENROLL = "unenroll"
    PENN_ID = "penn_id"
    USER_AGENT = "user_agent"


def cleanup_data(data_frame: DataFrame, action: Action) -> DataFrame:
    if action in {Action.CREATE, Action.REMOVE, Action.PENN_ID}:
        subset = "Pennkey" if action == Action.PENN_ID else "Email"
        data_frame.drop_duplicates(subset=[subset], inplace=True)
    return data_frame.astype("string", errors="ignore")


def get_timestamped_path(result_path: Path, open_test: bool) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    new_path_stem = f"{'TEST_' if open_test else ''}{result_path.stem}_{timestamp}.csv"
    new_path = RESULTS / new_path_stem
    if result_path.is_file():
        result_path.rename(new_path)
    else:
        Path.touch(new_path)
    return new_path


def get_enrollment_id_and_type(course_id, section_id):
    try:
        return int(section_id), True
    except Exception:
        return course_id, False


def get_penn_id_from_penn_key(penn_key: str) -> Optional[str]:
    cursor = get_data_warehouse_cursor()
    cursor.execute(
        "SELECT penn_id FROM person_all_v WHERE pennkey = :pennkey",
        pennkey=penn_key.strip().lower(),
    )
    for penn_id in cursor:
        return penn_id[0]
    return None


def email_in_use(user: User, email: str) -> bool:
    channels = [
        channel
        for channel in user.get_communication_channels()
        if channel.type == "email"
    ]
    return bool([channel for channel in channels if channel.address == email])


def find_user_by_email(account: Account, email: str) -> Optional[User]:
    users = (
        user
        for user in account.get_users(search_term=email)
        if user.login_id.lower() == email.lower() or email_in_use(user, email)
    )
    return next(users, None)


def create_user(
    account: Account, full_name: str, email: str
) -> tuple[Literal["already in use"] | Literal["created"], Optional[User]]:
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


def update_user_name(
    account: Account, new_name: str, email: str
) -> Literal["not found"] | Literal["updated"]:
    user = find_user_by_email(account, email)
    if not user:
        return "not found"
    else:
        user.edit(user={"name": new_name})
        return "updated"


def remove_user(
    account: Account, email: str
) -> Literal["not found"] | Literal["removed"]:
    user = find_user_by_email(account, email)
    if not user:
        return "not found"
    else:
        account.delete_user(user)
        return "removed"


@lru_cache
def get_canvas_section_or_course(
    canvas_id: str, section: bool, instance: Instance
) -> Section | Course | Literal["course not found"]:
    try:
        canvas_section = (
            get_section(canvas_id, instance=instance)
            if section
            else get_course(canvas_id, instance=instance)
        )
    except Exception:
        canvas_section = "course not found"
    return canvas_section


def get_enrollment_login(enrollment: Enrollment, instance: Instance) -> dict:
    try:
        user = get_user(enrollment.user["id"], instance=instance)
    except Exception:
        user = None
    return {
        "enrollment": enrollment,
        "login_id": user.login_id.lower() if user and user.login_id else "",
        "email": user.email.lower() if user and user.email else "",
    }


@lru_cache
def get_enrollments(canvas_section: Section | Course, instance: Instance) -> list[dict]:
    try:
        enrollments = [enrollment for enrollment in canvas_section.get_enrollments()]
        enrollments = [
            get_enrollment_login(enrollment, instance) for enrollment in enrollments
        ]
    except Exception:
        enrollments = []
    return enrollments


def get_enrollment_by_email(email: str, enrollments: list[dict]) -> Optional[dict]:
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
    account: Account,
    full_name: str,
    email: str,
    enrollment_type: Optional[str],
    canvas_id: str,
    section: Optional[bool],
    notify: Optional[bool],
    instance: Instance,
) -> Optional[tuple[Section | Course | str, Section | Course | Enrollment | str, str]]:
    user = find_user_by_email(account, email)
    if not user:
        user = create_user(account, full_name, email)[1]
    canvas_section = get_canvas_section_or_course(canvas_id, section, instance)
    if canvas_section == "course not found":
        return canvas_section, canvas_id, ""
    if not enrollment_type:
        return "invalid enrollment type", canvas_section, ""
    try:
        if isinstance(canvas_section, Section | Course):
            enrollment = canvas_section.enroll_user(
                user, enrollment={"notify": notify, "type": enrollment_type}
            )
            return "enrolled", enrollment, ""
    except Exception as error:
        return "failed to enroll", canvas_section, str(error)
    return None


def unenroll_user(
    email: str,
    canvas_id: str,
    section: Optional[bool],
    instance: Instance,
    task="conclude",
) -> tuple[Course | Section | str, Course | Section | Enrollment | str | dict]:
    task = task.lower() if task.lower() in UNENROLL_TASKS else "conclude"
    canvas_section = get_canvas_section_or_course(canvas_id, section, instance)
    if not canvas_section or canvas_section == "course not found":
        return canvas_section, canvas_id
    try:
        enrollments = get_enrollments(canvas_id, canvas_section, instance)
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


def process_result(result_path: Path):
    result = read_csv(result_path)
    penn_id = "penn_id" in str(result_path)
    penn_id_counts = counts = None
    if penn_id:
        penn_ids = DataFrame(result[result["Penn ID"].astype(str).str.isnumeric()])
        not_found = result[result["Penn ID"] == "not found"]
        error = DataFrame(
            result[result["Penn ID"].astype(str).str.contains("ERROR", regex=False)]
        )
        result = concat([error, not_found, penn_ids])
        penn_id_counts = (
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
    return penn_id_counts if penn_id else counts, penn_id


def print_messages(total: int, counts: tuple, penn_id: bool):
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
                f" {invalid_enrollment_type} "
                f"{'user' if missing_value == 1 else 'users'} with"
                " invalid enrollment types",
                "red",
                True,
            )


def open_canvas_bulk_action_main(verbose: bool, force: bool, test: bool):
    def perform_canvas_action(
        user: Series, verbose: bool, args: tuple[Account, Action]
    ):
        account, action = args
        full_name = ""
        email = ""
        enrollment_type = ""
        course_id = ""
        section_id = ""
        canvas_id = ""
        notify = ""
        notify_bool = None
        task = ""
        penn_key = ""
        section = None
        if action == Action.ENROLL:
            (
                index,
                full_name,
                email,
                enrollment_type,
                course_id,
                section_id,
                notify,
            ) = user[:-2]
            notify_bool = bool((lower := notify.lower()) == "true" or lower == "1")
            canvas_id, section = get_enrollment_id_and_type(course_id, section_id)
            enrollment_type = ENROLLMENT_TYPES.get(enrollment_type.lower(), "")
        elif action == Action.UNENROLL:
            index, full_name, email, course_id, section_id, task = user[:-1]
            canvas_id, section = get_enrollment_id_and_type(course_id, section_id)
        elif action == Action.PENN_ID:
            index, full_name, penn_key = user[:-1]
        elif action == Action.USER_AGENT:
            index, course_id = user
        else:
            index, full_name, email = user[:-1]
        status = "removed" if action == Action.REMOVE else "created"
        course = None
        error_message = False
        enroll_error = ""
        canvas_user = None
        try:
            for user in [full_name, email, penn_key]:
                if not isinstance(user, str):
                    raise Exception("missing value")
            if action in {Action.ENROLL, Action.UNENROLL} and not section:
                try:
                    int(course_id)
                except Exception:
                    raise Exception("missing value")
            if full_name:
                full_name = " ".join(full_name.strip().split())
            if email:
                email = email.strip()
            if action == Action.UNENROLL:
                status, course = unenroll_user(
                    email, canvas_id, section, instance, task
                )
            elif action == Action.ENROLL:
                enroll_results = enroll_user(
                    account,
                    full_name,
                    email,
                    enrollment_type,
                    canvas_id,
                    section,
                    notify_bool,
                    instance,
                )
                if enroll_results:
                    status, course, enroll_error = enroll_results
            elif action == Action.REMOVE:
                status = remove_user(account, email)
            elif action == Action.UPDATE:
                status = update_user_name(account, full_name, email)
            elif action == Action.PENN_ID:
                status = get_penn_id_from_penn_key(penn_key) or "not found"
            elif not action == Action.USER_AGENT:
                status, canvas_user = create_user(account, full_name, email)
        except Exception as error_status:
            status = f"ERROR: {str(error_status)}"
            error_message = True
        if action == Action.PENN_ID:
            users.at[index, ["Penn ID"]] = status
        else:
            users.at[index, ["Status"]] = status
        if enroll_error:
            users.at[index, ["Error"]] = enroll_error
        users.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)
        if verbose and error_message:
            action_display = "get Penn ID for" if action == Action.PENN_ID else action
            course_display = f" in course {course}" if course else ""
            message = color(
                "ERROR: Failed to"
                f" {action_display} {full_name} ({email}){course_display}: {status}.",
                "red",
            )
            print_item(index, TOTAL, message)
        elif verbose:
            if action == Action.PENN_ID:
                if error_message:
                    display_color = "red"
                else:
                    display_color = "green" if status != "not found" else "yellow"
            else:
                display_color = COLOR_MAP.get(status, "")
            message = ""
            print_item(index, TOTAL, message)
            name_display = color(full_name, "yellow")
            colon_display = ":" if canvas_user else ""
            status_display = color(status.upper(), display_color)
            user_display = (
                color(" " + str(canvas_user), "magenta") if canvas_user else ""
            )
            echo(f"{name_display}{colon_display} {status_display}{user_display}.")

    user_agent_courses = 0
    input_files, missing_file_message = find_input(
        "Open Canvas Bulk Action csv file", INPUT, date=False, open_canvas=True
    )
    RESULT_PATHS = list()
    input_files.sort(reverse=True)
    for index, input_file in enumerate(input_files):
        action = Action.CREATE
        display_action = "Creating"
        file_name = input_file.stem.lower()
        if "unenroll" in file_name:
            action = Action.UNENROLL
            display_action = "Unenrolling"
        elif "enroll" in file_name:
            action = Action.ENROLL
            display_action = "Enrolling"
        elif "remove" in file_name:
            action = Action.REMOVE
            display_action = "Removing"
        elif "update" in file_name:
            action = Action.UPDATE
            display_action = "Updating"
        elif "penn_id" in file_name:
            if not confirm_global_protect_enabled():
                continue
            action = Action.PENN_ID
            display_action = "Getting Penn IDs for"
        elif "user_agent" in file_name:
            action = Action.USER_AGENT
            display_action = "Getting user agent information for"
        open_test = test or "test" in file_name
        RESULT_STRING = f"{input_file.stem}_RESULT.csv"
        RESULT_PATH = RESULTS / RESULT_STRING
        START = get_start_index(force, RESULT_PATH)
        instance = Instance.OPEN_TEST if open_test else Instance.OPEN
        switch_logger_file(LOGS, "open_canvas_bulk_action", instance.name)
        if action == Action.ENROLL:
            action_headers = HEADERS[:]
            action_headers.insert(2, "Type")
        elif action == Action.UNENROLL:
            action_headers = HEADERS[:-1] + ["Task"]
        elif action == Action.PENN_ID:
            action_headers = HEADERS[:1] + ["Pennkey"]
        else:
            action_headers = HEADERS[:2]
        if action == Action.USER_AGENT:
            courses = read_csv(input_file)["Course ID"].tolist()
            user_agent_courses = len(courses)
            for course in courses:
                new_path = get_timestamped_path(RESULT_PATH, open_test)
                new_path = new_path.rename(
                    RESULTS / f"{new_path.stem}_COURSE_{course}.csv"
                )
                browser_main(
                    make_list(course),
                    instance_name=instance,
                    force=force,
                    verbose=verbose,
                    override_result_path=new_path,
                )
                new_path.rename(RESULTS / f"{new_path.stem}_COMPLETED.csv")
            RESULT_PATHS.append((input_file, None))
            input_file.rename(COMPLETED / input_file.name)
        else:
            users, TOTAL, dated_input_file = process_input(
                input_files,
                INPUT_FILE_NAME,
                INPUT,
                action_headers,
                cleanup_data,
                missing_file_message,
                args=action,
                start=START,
                open_canvas=True,
            )
            if action == Action.PENN_ID:
                users["Penn ID"] = ""
                RESULT_HEADERS = action_headers + ["Penn ID"]
            elif action == Action.USER_AGENT:
                RESULT_HEADERS = ["Canvas User ID", "Name", "Email"]
                users[RESULT_HEADERS] = ""
            else:
                users["Status"] = ""
                RESULT_HEADERS = action_headers + ["Status"]
                if action == Action.ENROLL:
                    users["Error"] = ""
                    RESULT_HEADERS = RESULT_HEADERS + ["Error"]
            make_csv_paths(RESULT_PATH, make_index_headers(RESULT_HEADERS))
            print_skip_message(START, "user")
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
            ARGS = (get_account(get_main_account_id(instance)), action)
            if verbose:
                echo(f"==== FILE {index + 1}/{len(input_files)} ====")
                echo(color(input_file.stem, "blue"))
            if verbose:
                for user in users.itertuples():
                    perform_canvas_action(user, verbose, ARGS)
            else:
                with progressbar(
                    users.itertuples(), length=len(users.index)
                ) as progress:
                    for user in progress:
                        perform_canvas_action(user, verbose, ARGS)
            new_path = get_timestamped_path(RESULT_PATH, open_test)
            RESULT_PATHS.append((new_path, TOTAL))
            dated_input_file.rename(COMPLETED / dated_input_file.name)
    echo(color("SUMMARY:", "yellow"))
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
    echo(color("FINISHED", "yellow"))
