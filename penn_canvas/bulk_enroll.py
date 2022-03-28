from csv import writer
from datetime import datetime, timedelta

from pandas import DataFrame, read_csv
from typer import Exit, echo

from .api import (
    Instance,
    format_instance_name,
    get_account,
    get_course,
    get_main_account_id,
    get_user,
    validate_instance_name,
)
from .helpers import (
    BASE_PATH,
    YEAR,
    color,
    create_directory,
    find_input,
    get_processed,
    handle_clear_processed,
    make_csv_paths,
    process_input,
    switch_logger_file,
)

INPUT_FILE_NAME = "Terms input file"
COMMAND_PATH = create_directory(BASE_PATH / "Storage")
INPUT = create_directory(COMMAND_PATH / "Input")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")
PROCESSED = create_directory(COMMAND_PATH / ".processed")
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
    user: int,
    sub_account: int,
    terms: list[int],
    input_file: bool,
    dry_run: bool,
    instance_name: str | Instance,
    check_errors: bool,
    clear_processed: bool,
):
    instance = validate_instance_name(instance_name)
    switch_logger_file(LOGS, "bulk_enroll", instance.name)
    try:
        user_name = get_user(user, instance=instance).name
    except Exception:
        echo(
            color(
                f"- ERROR: User {user} not found. Please verify that you have the"
                " correct Canvas user id and try again.",
                "yellow",
            )
        )
        raise Exit()
    account = get_account(get_main_account_id(instance))
    sub_account = get_account(sub_account).name
    prefix = f"{YEAR}_bulk_enroll_{user_name}_in_{sub_account}_"
    processed_stem_string = (
        f"{prefix}processed_courses{format_instance_name(instance)}.csv"
    )
    processed_path = PROCESSED / processed_stem_string
    processed_errors_stem_string = (
        f"{prefix}processed_errors{format_instance_name(instance)}.csv"
    )
    processed_errors_path = PROCESSED / processed_errors_stem_string
    handle_clear_processed(
        clear_processed, [processed_path, processed_errors_path], item_plural="courses"
    )
    processed_courses = get_processed(processed_path, PROCESSED_HEADERS)
    processed_errors = get_processed(processed_errors_path, PROCESSED_HEADERS)
    if input_file:
        input_files, missing_file_message = find_input(
            INPUT_FILE_NAME, INPUT, date=False, bulk_enroll=True
        )
        terms = process_input(
            input_files,
            INPUT_FILE_NAME,
            INPUT,
            ["canvas_term_id"],
            cleanup_data,
            missing_file_message,
            bulk_enroll=True,
        )
    already_processed_count = (
        len(processed_courses)
        if check_errors
        else len(processed_courses) + len(processed_errors)
    )
    if already_processed_count:
        message = color(
            f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
            f" {'COURSE' if already_processed_count == 1 else 'COURSES'}...",
            "yellow",
        )
        echo(f") {message}")
    TOTAL = len(terms)
    TOMORROW = get_tomorrow()
    LOG_PATH = LOGS / f"{YEAR}_bulk_enrollment_log_{user_name}_in_{sub_account}.csv"
    echo(f") Finding {sub_account} courses for {TOTAL} terms...")
    COURSES = list()
    for term in terms:
        COURSES.extend(
            [
                course
                for course in account.get_courses(
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
            / f"{sub_account}_courses_for_bulk_enrollment_of_{user_name}_{YEAR}.csv",
            index=False,
        )
    else:
        COURSES = [
            course for course in COURSES if str(course.id) not in processed_courses
        ]
        if not check_errors:
            COURSES = [
                course for course in COURSES if str(course.id) not in processed_errors
            ]
        ERROR_FILE = (
            RESULTS / f"{sub_account}_bulk_enrollment_{user_name}_{YEAR}_ERRORS.csv"
        )
        make_csv_paths(ERROR_FILE, HEADERS)
        make_csv_paths(LOG_PATH, LOG_HEADERS)
        echo(f") Enrolling {user_name} in {sub_account} courses...")
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
                updated_course = get_course(course.id, instance=instance)
                if updated_course.enrollment_term_id == enrollment_term_id and bool(
                    updated_course.end_at
                ) == bool(end_at):
                    errors = read_csv(ERROR_FILE)
                    errors = errors[
                        errors["canvas sis course id"] != sis_course_id_or_name
                    ]
                    errors.to_csv(ERROR_FILE, index=False)
                    log_file = read_csv(LOG_PATH)
                    log_file.drop(index=log_file.index[-1:], inplace=True)
                    log_file.to_csv(LOG_PATH, index=False)

                    echo(
                        f"- ({index}/{TOTAL_COURSES})"
                        f" {color('ENROLLED', 'green')} {color(user_name)} in"
                        f" {color(course.name, 'blue')}."
                    )
                else:
                    echo(
                        "- ({index}/{TOTAL_COURSES}) {color('ERROR:', 'red')}"
                        " Failed to restore original term and/or end_at data. Please"
                        f" see log path for details: {color(LOG_PATH, 'green')}"
                    )
                if str(course.id) in processed_errors:
                    processed_errors_csv = read_csv(processed_errors_path)
                    processed_errors_csv = processed_errors_csv[
                        processed_errors_csv["canvas sis course id"]
                        != sis_course_id_or_name
                    ]
                    processed_errors_csv.to_csv(processed_errors_path, index=False)

                with open(processed_path, "a+", newline="") as processed_file:
                    writer(processed_file).writerow([course.id, sis_course_id_or_name])
            except Exception as error:
                color(
                    f"- ({index}/{TOTAL_COURSES}) ERROR: Failed to enroll"
                    f" {user_name} in {course.name} ({error})",
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
                if str(course.id) not in processed_errors:
                    with open(
                        processed_errors_path, "a+", newline=""
                    ) as processed_file:
                        writer(processed_file).writerow(
                            [course.id, sis_course_id_or_name]
                        )
    color("FINISHED", "yellow", True)
