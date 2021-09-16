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
HEADERS = [
    "canvas_course_id",
    "course_id",
    "short_name",
    "account_id",
    "term_id",
    "status",
    "published ungraded quizzes",
    "unpublished ungraded quizzes",
    "published graded quizzes",
    "unpublished graded quizzes",
    "total",
]
CLEANUP_HEADERS = [header.replace(" ", "_") for header in HEADERS[:6]]


def cleanup_data(data):
    data.drop_duplicates(subset=["canvas_course_id"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")

    return data


def filter_and_count_quizzes(quizzes, quiz_type, published):
    return len(
        [
            quiz
            for quiz in quizzes
            if quiz.quiz_type == quiz_type and quiz.published is published
        ]
    )


def process_result(result_path):
    result = read_csv(result_path)
    courses_with_quiz = len(
        result[(result["total"] != 0) & (result["total"] != "error")].index
    )
    result.fillna("N/A", inplace=True)
    result.drop(columns=["index"], inplace=True)
    result.sort_values(by=["total"], inplace=True, ascending=False)
    result.to_csv(result_path, index=False)

    return courses_with_quiz


def print_messages(total, courses_with_quiz):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total)} courses.")
    echo(
        f"- Found {colorize(courses_with_quiz, 'green')} courses with at least one"
        " quiz."
    )
    colorize("FINISHED", "yellow", True)


def count_quizzes_main(test, force, verbose):
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
            quizzes = course.get_quizzes()
            published_ungraded_quizzes = filter_and_count_quizzes(
                quizzes, "survey", True
            )
            unpublished_ungraded_quizzes = filter_and_count_quizzes(
                quizzes, "survey", False
            )
            published_graded_quizzes = filter_and_count_quizzes(
                quizzes, "graded_survey", True
            )
            unpublished_graded_quizzes = filter_and_count_quizzes(
                quizzes, "graded_survey", False
            )
            total_quizzes = (
                published_ungraded_quizzes
                + unpublished_ungraded_quizzes
                + published_graded_quizzes
                + unpublished_graded_quizzes
            )
        except Exception as error:
            published_ungraded_quizzes = "error"
            unpublished_ungraded_quizzes = "error"
            published_graded_quizzes = "error"
            unpublished_graded_quizzes = "error"
            course_name = canvas_course_id
            error_message = error

        report.at[index, HEADERS] = [
            canvas_course_id,
            course_id,
            short_name,
            account_id,
            term_id,
            status,
            published_ungraded_quizzes,
            unpublished_ungraded_quizzes,
            published_graded_quizzes,
            unpublished_graded_quizzes,
            total_quizzes,
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        echo(
            f"- ({index + 1}/{TOTAL})"
            f" {colorize(course_name, 'yellow')}:"
            f" {colorize(total_quizzes if not error_message else error_message, 'blue' if not error_message else 'red')}"
        )

    reports, please_add_message, missing_file_message = find_input(
        COMMAND, INPUT_FILE_NAME, REPORTS
    )
    RESULT_PATH = RESULTS / f"{YEAR}_quiz_result.csv"
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
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing courses...")
    toggle_progress_bar(report, count_quizzes_for_course, CANVAS, verbose)
    courses_with_quiz = process_result(RESULT_PATH)
    print_messages(TOTAL, courses_with_quiz)
