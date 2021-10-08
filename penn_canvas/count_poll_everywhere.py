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

COMMAND = "Count Poll Everywhere"
INPUT_FILE_NAME = "Canvas Provisioning (Courses) report"
REPORTS, RESULTS = get_command_paths(COMMAND)
HEADERS = [
    "canvas_course_id",
    "course_id",
    "short_name",
    "account_id",
    "term_id",
    "status",
    "poll everywhere",
]
CLEANUP_HEADERS = [header.replace(" ", "_") for header in HEADERS[:6]]


def cleanup_data(data):
    data.drop_duplicates(subset=["canvas_course_id"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")

    return data


def pollev_in_external_url(item):
    try:
        return "pollev" in item.external_url
    except Exception:
        return False


def process_result(result_path, term_id):
    result = read_csv(result_path, dtype=str)
    courses_with_poll_everywhere = len(result[result["poll everywhere"] == "Y"].index)
    result.drop(columns=["index"], inplace=True)
    renamed_headers = [header.replace("_", " ") for header in HEADERS[:5]]
    renamed_columns = {}

    for index, header in enumerate(renamed_headers):
        renamed_columns[HEADERS[index]] = header

    result.rename(columns=renamed_columns, inplace=True)
    result.sort_values("poll everywhere", ascending=False, inplace=True)
    result.fillna("N/A", inplace=True)
    result.to_csv(result_path, index=False)
    result_path.rename(str(result_path).replace(YEAR, term_id))

    return courses_with_poll_everywhere


def print_messages(total, courses_with_quiz):
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total)} courses.")
    echo(
        f"- Found {colorize(courses_with_quiz, 'green')} courses with Poll Everywhere"
        " enabled."
    )
    colorize("FINISHED", "yellow", True)


def count_poll_everywhere_main(test, force, verbose):
    def count_poll_everywhere_for_course(course, canvas, verbose):
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
            modules = [module for module in course.get_modules()]
            items = [
                item
                for module in modules
                for item in module.get_module_items()
                if pollev_in_external_url(item)
            ]
            poll_everywhere = "Y" if items else "N"
        except Exception as error:
            course_name = canvas_course_id
            poll_everywhere = "error"
            error_message = error

        report.at[index, HEADERS] = [
            canvas_course_id,
            course_id,
            short_name,
            account_id,
            term_id,
            status,
            poll_everywhere,
        ]
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if verbose:
            text_and_color = (
                ("FOUND", "green")
                if poll_everywhere == "Y"
                else ("NOT FOUND", "yellow")
            )
            message = f"{colorize(text_and_color[0], text_and_color[1])}"

            if not error_message:
                echo(f"- ({(index + 1):,}/{TOTAL}) {colorize(course_name)}: {message}")
            else:
                echo(
                    f"- ({(index + 1):,}/{TOTAL})"
                    f" {colorize(course_name)}:"
                    f" {colorize(error_message, 'red')}"
                )

    reports, please_add_message, missing_file_message = find_input(
        INPUT_FILE_NAME, REPORTS
    )
    RESULT_PATH = RESULTS / f"{YEAR}_poll_everywhere_usage_report.csv"
    START = get_start_index(force, RESULT_PATH, RESULTS)
    report, TOTAL = process_input(
        reports,
        INPUT_FILE_NAME,
        REPORTS,
        CLEANUP_HEADERS,
        cleanup_data,
        missing_file_message,
        start=START,
    )
    TERM_ID = report.at[0, "term_id"]
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    echo(") Processing courses...")
    toggle_progress_bar(report, count_poll_everywhere_for_course, CANVAS, verbose)
    courses_with_poll_everywhere = process_result(RESULT_PATH, TERM_ID)
    print_messages(TOTAL, courses_with_poll_everywhere)
