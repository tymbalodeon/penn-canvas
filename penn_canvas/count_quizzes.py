from typer import echo
from pandas import read_csv
from .helpers import (
    YEAR,
    find_input,
    make_skip_message,
    toggle_progress_bar,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    process_input,
)

COMMAND = "Count Quizzes"
INPUT_FILE_NAME = "Canvas Provisioning (Courses) report"
REPORTS, RESULTS = get_command_paths(COMMAND)
HEADERS = [
    "canvas course id",
    "course id",
    "short name",
    "account id",
    "term id",
    "status",
    "published_ungraded_quizzes",
    "unpublished_ungraded_quizzes",
    "published_graded_quizzes",
    "unpublished_graded_quizzes",
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


def process_result(result_path, processed_path, new):
    result = read_csv(result_path)
    return result


def count_quizzes_main(test, force, verbose):
    def count_quizzes_for_course(course, canvas, verbose):
        index, canvas_course_id, course_id, short_name, account, term, status = course

        try:
            course = canvas.get_course(canvas_course_id)
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

            print(
                index,
                canvas_course_id,
                course_id,
                account,
                term,
                status,
                published_ungraded_quizzes,
                unpublished_ungraded_quizzes,
                published_graded_quizzes,
                unpublished_graded_quizzes,
                total_quizzes,
            )
        except Exception as error:
            print(error)

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
        START,
    )
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing courses...")
    toggle_progress_bar(report, count_quizzes_for_course, CANVAS, verbose)
