from csv import writer

from pandas import DataFrame
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
INPUT, RESULTS = get_command_paths(COMMAND)


def cleanup_data(data):
    return data["canvas_term_id"].tolist()


def bulk_enroll_main(user, sub_account, terms, input_file, dry_run, test):
    INPUT_FILES, PLEASE_ADD_MESSAGE, MISSING_FILE_MESSAGE = find_input(
        COMMAND, INPUT_FILE_NAME, INPUT, date=False, bulk_enroll=True
    )

    if input_file:
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
    SUB_ACCOUNT = CANVAS.get_account(sub_account)

    try:
        USER_NAME = CANVAS.get_user(user)
    except Exception:
        colorize(f"- ERROR: User {user} not found.", "yellow", True)

        raise Exit(1)

    if dry_run:
        echo(f") Finding {SUB_ACCOUNT} courses for {TOTAL} terms...")
    else:
        echo(f") Enrolling {USER_NAME} in {SUB_ACCOUNT} courses for {TOTAL} terms...")

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
        ERROR_FILE = (
            RESULTS / f"{SUB_ACCOUNT}_bulk_enrollment_{USER_NAME}_{YEAR}_ERRORS.csv"
        )
        make_csv_paths(
            RESULTS, ERROR_FILE, ["canvas sis course id", "canvas course id", "error"]
        )

        for course in COURSES:
            try:
                enrollment = course.enroll_user(
                    user, enrollment={"enrollment_state": "active"}
                )
                echo(f"- ENROLLED {USER_NAME} in {course.name}: {enrollment}")
            except Exception as error:
                colorize(
                    f"- ERROR: Failed to enroll {USER_NAME} in {course.name} ({error})",
                    "red",
                    True,
                )
                with open(ERROR_FILE) as error_file:
                    writer(error_file).writerow(
                        [
                            course.sis_course_id
                            if course.sis_course_id
                            else course.name,
                            course.id,
                            error,
                        ]
                    )

    colorize("FINISHED", "yellow", True)
