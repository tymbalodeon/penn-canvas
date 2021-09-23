from pandas import read_csv
from typer import echo

from .helpers import (
    YEAR,
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

COMMAND = "Count Quizzes"
INPUT_FILE_NAME = "Canvas Provisioning (Courses) report"
REPORTS, RESULTS = get_command_paths(COMMAND)
NEW_QUIZ_HEADERS = [
    "canvas_course_id",
    "course_id",
    "short_name",
    "account_id",
    "term_id",
    "status",
    "number of students",
    "total",
]
HEADERS = [
    "canvas_course_id",
    "course_id",
    "short_name",
    "account_id",
    "term_id",
    "status",
    "number of students",
    "published surveys",
    "unpublished surveys",
    "published graded surveys",
    "unpublished graded surveys",
    "published assignments",
    "unpublished assignments",
    "total published quizzes",
    "total unpublished quizzes",
    "total",
]
CLEANUP_HEADERS = [header.replace(" ", "_") for header in HEADERS[:6]]


def print_course(total_quizzes, error_message, index, total, course_name):
    found = (
        colorize(f"FOUND ({total_quizzes})", "green")
        if total_quizzes
        else colorize("NOT FOUND", "yellow")
    )
    echo(
        f"- ({(index + 1):,}/{total})"
        f" {colorize(course_name, 'magenta')}:"
        f" {colorize(error_message, 'red') if error_message else found}"
    )


def cleanup_data(data):
    data.drop_duplicates(subset=["canvas_course_id"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")

    return data


def filter_and_count_quizzes(quizzes, quiz_type, published):
    if not quiz_type:
        return len(
            [
                quiz
                for quiz in quizzes
                if quiz.quiz_type != "practice_quiz" and quiz.published is published
            ]
        )
    else:
        return len(
            [
                quiz
                for quiz in quizzes
                if quiz.quiz_type == quiz_type and quiz.published is published
            ]
        )


def is_new_quiz_assignment(assignment):
    try:
        if assignment.is_quiz_lti_assignment:
            return True
    except Exception:
        return False


def process_result(result_path, term_id):
    result = read_csv(result_path, dtype=str)
    courses_with_quiz = len(
        result[(result["total"] != "0") & (result["total"] != "error")].index
    )
    result.drop(columns=["index"], inplace=True)
    renamed_headers = [header.replace("_", " ") for header in HEADERS[:5]]
    renamed_columns = {}

    for index, header in enumerate(renamed_headers):
        renamed_columns[HEADERS[index]] = header

    result.rename(columns=renamed_columns, inplace=True)
    result.sort_values("total", ascending=False, inplace=True)
    result.fillna("N/A", inplace=True)
    result.to_csv(result_path, index=False)
    result_path.rename(str(result_path).replace(YEAR, term_id))

    return courses_with_quiz


def print_messages(total, courses_with_quiz):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total)} courses.")
    echo(
        f"- Found {colorize(courses_with_quiz, 'green')} courses with at least one"
        " quiz."
    )
    colorize("FINISHED", "yellow", True)


def count_quizzes_main(new_quizzes, test, force, verbose):
    def count_new_quizzes_for_course(course, canvas, verbose):
        (
            index,
            canvas_course_id,
            course_id,
            short_name,
            account_id,
            term_id,
            status,
        ) = course

        error_message = False

        try:
            course = canvas.get_course(canvas_course_id)
            course_name = course.name
            number_of_students = len(
                [student for student in course.get_users(enrollment_type=["student"])]
            )
            quizzes = [
                assignment
                for assignment in course.get_assignments()
                if is_new_quiz_assignment(assignment)
            ]

            total_quizzes = len(quizzes)
        except Exception as error:
            total_quizzes = "error"
            number_of_students = "error"
            course_name = canvas_course_id
            error_message = error

        report.at[index, NEW_QUIZ_HEADERS] = [
            canvas_course_id,
            course_id,
            short_name,
            account_id,
            term_id,
            status,
            str(number_of_students),
            str(total_quizzes),
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            print_course(total_quizzes, error_message, index, TOTAL, course_name)

    def count_quizzes_for_course(course, canvas, verbose):
        (
            index,
            canvas_course_id,
            course_id,
            short_name,
            account_id,
            term_id,
            status,
        ) = course

        error_message = False

        try:
            course = canvas.get_course(canvas_course_id)
            course_name = course.name
            number_of_students = len(
                [student for student in course.get_users(enrollment_type=["student"])]
            )
            quizzes = course.get_quizzes()
            published_ungraded_surveys = filter_and_count_quizzes(
                quizzes, "survey", True
            )
            unpublished_ungraded_surveys = filter_and_count_quizzes(
                quizzes, "survey", False
            )
            published_graded_surveys = filter_and_count_quizzes(
                quizzes, "graded_survey", True
            )
            unpublished_graded_surveys = filter_and_count_quizzes(
                quizzes, "graded_survey", False
            )
            published_assignments = filter_and_count_quizzes(
                quizzes, "assignment", True
            )
            unpublished_assignments = filter_and_count_quizzes(
                quizzes, "assignment", False
            )
            total_published_quizzes = filter_and_count_quizzes(quizzes, False, True)
            total_unpublished_quizzes = filter_and_count_quizzes(quizzes, False, False)
            total_quizzes = (
                published_ungraded_surveys
                + unpublished_ungraded_surveys
                + published_graded_surveys
                + unpublished_graded_surveys
                + published_assignments
                + unpublished_assignments
            )
        except Exception as error:
            published_ungraded_surveys = "error"
            unpublished_ungraded_surveys = "error"
            published_graded_surveys = "error"
            unpublished_graded_surveys = "error"
            published_assignments = "error"
            unpublished_assignments = "error"
            total_published_quizzes = "error"
            total_unpublished_quizzes = "error"
            course_name = canvas_course_id
            error_message = error

        report.at[index, HEADERS] = [
            canvas_course_id,
            course_id,
            short_name,
            account_id,
            term_id,
            status,
            str(number_of_students),
            str(published_ungraded_surveys),
            str(unpublished_ungraded_surveys),
            str(published_graded_surveys),
            str(unpublished_graded_surveys),
            str(published_assignments),
            str(unpublished_assignments),
            str(total_published_quizzes),
            str(total_unpublished_quizzes),
            str(total_quizzes),
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            print_course(total_quizzes, error_message, index, TOTAL, course_name)

    reports, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS
    )
    RESULT_PATH = (
        RESULTS / f"{YEAR}_{'new_' if new_quizzes else ''}quiz_usage_report.csv"
    )
    START = get_start_index(force, RESULT_PATH, RESULTS)
    report, TOTAL = process_input(
        reports,
        INPUT_FILE_NAME,
        REPORTS,
        please_add_message,
        CLEANUP_HEADERS,
        cleanup_data,
        missing_file_message,
        start=START,
    )
    TERM_ID = report.at[0, "term_id"]
    make_csv_paths(
        RESULTS,
        RESULT_PATH,
        make_index_headers(NEW_QUIZ_HEADERS if new_quizzes else HEADERS),
    )
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing courses...")

    if new_quizzes:
        toggle_progress_bar(report, count_new_quizzes_for_course, CANVAS, verbose)
    else:
        toggle_progress_bar(report, count_quizzes_for_course, CANVAS, verbose)

    courses_with_quiz = process_result(RESULT_PATH, TERM_ID)
    print_messages(TOTAL, courses_with_quiz)
