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
    get_processed,
    handle_clear_processed,
    make_csv_paths,
    process_input,
)

COMMAND = "Bulk Enroll"
INPUT_FILE_NAME = "Terms input file"
INPUT, RESULTS, LOGS, PROCESSED = get_command_paths(COMMAND, logs=True, processed=True)
ONGOING_TERM_ID = 4373
HEADERS = ["canvas course id", "canvas sis course id", "error"]
PROCESSED_HEADERS = HEADERS[:2]
LOG_HEADERS = HEADERS[:2]
LOG_HEADERS.extend(["term", "end_at"])


def get_tomorrow():
    current_time = datetime.utcnow()
    now_plus_one_day = current_time + timedelta(days=1)

    return now_plus_one_day.isoformat() + "Z"


def cleanup_data(data):
    return data["canvas_term_id"].tolist()


def bulk_enroll_main(
    user, sub_account, terms, input_file, dry_run, test, check_errors, clear_processed
):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    try:
        USER_NAME = CANVAS.get_user(user).name
    except Exception:
        colorize(
            f"- ERROR: User {user} not found. Please verify that you have the correct"
            " Canvas user id and try again.",
            "yellow",
            True,
        )

        raise Exit()

    ACCOUNT = CANVAS.get_account(MAIN_ACCOUNT_ID)
    SUB_ACCOUNT = CANVAS.get_account(sub_account).name
    PROCESSED_STEM_STRING = (
        f"{YEAR}_bulk_enroll_{USER_NAME}_in_{SUB_ACCOUNT}_"
        f"processed_courses{'_test' if test else ''}.csv"
    )
    PROCESSED_PATH = PROCESSED / PROCESSED_STEM_STRING
    PROCESSED_ERRORS_STEM_STRING = (
        f"{YEAR}_bulk_enroll_{USER_NAME}_in_{SUB_ACCOUNT}_"
        f"processed_errors{'_test' if test else ''}.csv"
    )
    PROCESSED_ERRORS_PATH = PROCESSED / PROCESSED_ERRORS_STEM_STRING
    handle_clear_processed(
        clear_processed, [PROCESSED_PATH, PROCESSED_ERRORS_PATH], item_plural="courses"
    )
    PROCESSED_COURSES = get_processed(PROCESSED, PROCESSED_PATH, PROCESSED_HEADERS)
    PROCESSED_ERRORS = get_processed(
        PROCESSED, PROCESSED_ERRORS_PATH, PROCESSED_HEADERS
    )

    if input_file:
        INPUT_FILES, MISSING_FILE_MESSAGE = find_input(
            INPUT_FILE_NAME, INPUT, date=False, bulk_enroll=True
        )
        terms = process_input(
            INPUT_FILES,
            INPUT_FILE_NAME,
            INPUT,
            ["canvas_term_id"],
            cleanup_data,
            MISSING_FILE_MESSAGE,
            bulk_enroll=True,
        )

    already_processed_count = (
        len(PROCESSED_COURSES)
        if check_errors
        else len(PROCESSED_COURSES) + len(PROCESSED_ERRORS)
    )

    if already_processed_count:
        message = colorize(
            f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
            f" {'COURSE' if already_processed_count == 1 else 'COURSES'}...",
            "yellow",
        )
        echo(f") {message}")

    TOTAL = len(terms)
    TOMORROW = get_tomorrow()

    LOG_PATH = LOGS / f"{YEAR}_bulk_enrollment_log_{USER_NAME}_in_{SUB_ACCOUNT}.csv"

    echo(f") Finding {SUB_ACCOUNT} courses for {TOTAL} terms...")

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

    if dry_run:
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
        COURSES = [
            course for course in COURSES if str(course.id) not in PROCESSED_COURSES
        ]

        if not check_errors:
            COURSES = [
                course for course in COURSES if str(course.id) not in PROCESSED_ERRORS
            ]

        ERROR_FILE = (
            RESULTS / f"{SUB_ACCOUNT}_bulk_enrollment_{USER_NAME}_{YEAR}_ERRORS.csv"
        )
        make_csv_paths(RESULTS, ERROR_FILE, HEADERS)
        make_csv_paths(LOGS, LOG_PATH, LOG_HEADERS)

        echo(f") Enrolling {USER_NAME} in {SUB_ACCOUNT} courses...")

        TOTAL_COURSES = len(COURSES)

        for index, course in enumerate(COURSES):
            index += 1
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
                    course.end_at,
                ]

                with open(LOG_PATH, "a", newline="") as log:
                    writer(log).writerow(course_info)

                if course.end_at:
                    end_at = course.end_at
                    course.update(course={"end_at": TOMORROW})

                course.update(course={"term_id": ONGOING_TERM_ID})
                course.enroll_user(user, enrollment={"enrollment_state": "active"})
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
                        f"- ({index}/{TOTAL_COURSES})"
                        f" {colorize('ENROLLED', 'green')} {colorize(USER_NAME)} in"
                        f" {colorize(course.name, 'blue')}."
                    )

                else:
                    echo(
                        "- ({index}/{TOTAL_COURSES}) {colorize('ERROR:', 'red')}"
                        " Failed to restore original term and/or end_at data. Please"
                        f" see log path for details: {colorize(LOG_PATH, 'green')}"
                    )

                if str(course.id) in PROCESSED_ERRORS:
                    processed_errors_csv = read_csv(PROCESSED_ERRORS_PATH)
                    processed_errors_csv = processed_errors_csv[
                        processed_errors_csv["canvas sis course id"]
                        != sis_course_id_or_name
                    ]
                    processed_errors_csv.to_csv(PROCESSED_ERRORS_PATH, index=False)

                with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                    writer(processed_file).writerow([course.id, sis_course_id_or_name])
            except Exception as error:
                colorize(
                    f"- ({index}/{TOTAL_COURSES}) ERROR: Failed to enroll"
                    f" {USER_NAME} in {course.name} ({error})",
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

                if str(course.id) not in PROCESSED_ERRORS:
                    with open(
                        PROCESSED_ERRORS_PATH, "a+", newline=""
                    ) as processed_file:
                        writer(processed_file).writerow(
                            [course.id, sis_course_id_or_name]
                        )

    colorize("FINISHED", "yellow", True)
