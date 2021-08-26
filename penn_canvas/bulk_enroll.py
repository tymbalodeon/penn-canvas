from csv import writer
from datetime import datetime, timedelta

from pandas import DataFrame, read_csv
from typer import Exit, echo
from .helpers import (
    MAIN_ACCOUNT_ID,
    YEAR,
    colorize,
    find_input,
    get_canvas,
    get_command_paths,
    make_csv_paths,
    process_input,
)

COMMAND = "Bulk Enroll"
INPUT_FILE_NAME = "Terms input file"
INPUT, RESULTS, LOGS = get_command_paths(COMMAND, logs=True)
ONGOING_TERM_ID = 4373
HEADERS = ["canvas course id", "canvas sis course id", "error"]
LOG_HEADERS = HEADERS[:]
LOG_HEADERS.append("end_at")


def get_tomorrow():
    current_time = datetime.utcnow()
    now_plus_one_day = current_time + timedelta(days=1)

    return now_plus_one_day.isoformat() + "Z"


def cleanup_data(data):
    return data["canvas_term_id"].tolist()


def bulk_enroll_main(user, sub_account, terms, input_file, dry_run, test):
    if input_file:
        INPUT_FILES, PLEASE_ADD_MESSAGE, MISSING_FILE_MESSAGE = find_input(
            COMMAND, INPUT_FILE_NAME, INPUT, date=False, bulk_enroll=True
        )
        terms = process_input(
            INPUT_FILES,
            INPUT_FILE_NAME,
            INPUT,
            PLEASE_ADD_MESSAGE,
            ["canvas_term_id"],
            cleanup_data,
            MISSING_FILE_MESSAGE,
            bulk_enroll=True,
        )

    TOTAL = len(terms)
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    ACCOUNT = CANVAS.get_account(MAIN_ACCOUNT_ID)
    SUB_ACCOUNT = CANVAS.get_account(sub_account).name
    TOMORROW = get_tomorrow()

    try:
        USER_NAME = CANVAS.get_user(user).name
    except Exception:
        colorize(
            f"- ERROR: User {user} not found. Please verify that you have the correct"
            " Canvas user id and try again.",
            "yellow",
            True,
        )

        raise Exit(1)

    LOG_PATH = LOGS / f"{YEAR}_bulk_enrollment_log_{USER_NAME}_in_{SUB_ACCOUNT}.csv"

    echo(f") Finding {SUB_ACCOUNT} courses for {TOTAL} terms...")

    if dry_run:
        COURSES = list()

        for term in terms:
            COURSES.extend(
                [
                    course
                    for course in ACCOUNT.get_courses(
                        enrollment_term_id=term, by_subaccounts=[sub_account]
                    )
                ]
            )
        course_codes = [
            course.sis_course_id if course.sis_course_id else course.name
            for course in COURSES
        ]
        dry_run_output = DataFrame(course_codes, columns=["course"])
        dry_run_output.to_csv(
            RESULTS
            / f"{SUB_ACCOUNT}_courses_for_bulk_enrollment_of_{USER_NAME}_{YEAR}.csv",
            index=False,
        )
    else:
        ERROR_FILE = (
            RESULTS / f"{SUB_ACCOUNT}_bulk_enrollment_{USER_NAME}_{YEAR}_ERRORS.csv"
        )
        make_csv_paths(RESULTS, ERROR_FILE, HEADERS)
        make_csv_paths(LOGS, LOG_PATH, LOG_HEADERS)

        echo(f") Enrolling {USER_NAME} in {SUB_ACCOUNT} courses...")

        for term in terms:
            for course in ACCOUNT.get_courses(
                enrollment_term_id=term, by_subaccounts=[sub_account]
            ):
                sis_course_id_or_name = (
                    course.sis_course_id if course.sis_course_id else course.name
                )

                try:
                    enrollment_term_id = course.enrollment_term_id
                    end_at = ""

                    course_info = [
                        course.id,
                        sis_course_id_or_name,
                        enrollment_term_id,
                        end_at,
                    ]

                    with open(LOG_PATH, "a", newline="") as log:
                        writer(log).writerow(course_info)

                    if course.end_at:
                        end_at = course.end_at
                        course.update(course={"end_at": TOMORROW})

                    course.update(course={"term_id": ONGOING_TERM_ID})
                    enrollment = course.enroll_user(
                        user, enrollment={"enrollment_state": "active"}
                    )
                    course.update(course={"term_id": enrollment_term_id})

                    if end_at:
                        course.update(course={"end_at": end_at})

                    updated_course = CANVAS.get_course(course.id)

                    if updated_course.enrollment_term_id == enrollment_term_id and bool(
                        updated_course.end_at
                    ) == bool(end_at):
                        errors = read_csv(ERROR_FILE)
                        errors = errors[
                            errors["canvas sis course id"] != sis_course_id_or_name
                        ]
                        errors.to_csv(ERROR_FILE, index=False)
                        log = read_csv(LOG_PATH)
                        log.drop(index=log.index[-1:], inplace=True)
                        log.to_csv(LOG_PATH, index=False)

                        echo(
                            f"- {colorize('ENROLLED', 'green')} {colorize(USER_NAME)} in"
                            f" {colorize(course.name, 'blue')}"
                        )
                    else:
                        echo(
                            "- ERROR: Failed to restore original term and/or end_at"
                            f" data. Please see log path for details: {LOG_PATH}"
                        )
                except Exception as error:
                    colorize(
                        f"- ERROR: Failed to enroll {USER_NAME} in"
                        f" {course.name} ({error})",
                        "red",
                        True,
                    )

                    with open(ERROR_FILE, "a+", newline="") as error_file:
                        errors = set(read_csv(ERROR_FILE)["canvas sis course id"])

                        if sis_course_id_or_name not in errors:
                            writer(error_file).writerow(
                                [
                                    course.id,
                                    sis_course_id_or_name,
                                    error,
                                ]
                            )

    colorize("FINISHED", "yellow", True)
