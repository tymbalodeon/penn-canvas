from csv import writer
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    colorize,
    colorize_path,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_skip_message,
    toggle_progress_bar,
)

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS = get_command_paths("tool")
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_tool_result.csv"
HEADERS = [
    "index",
    "canvas_course_id",
    "course_id",
    "canvas_account_id",
    "term_id",
    "status",
    "found",
]


def find_course_report():
    typer.echo(") Finding Canvas Provisioning (Courses) report(s)...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = typer.style(
            "- ERROR: Canvas tool reports directory not found.", fg=typer.colors.YELLOW
        )
        typer.echo(
            f"{error} \n- Creating one for you at: {colorize_path(str(REPORTS))}\n-"
            " Please add a Canvas Provisioning (Courses) report for at least one term, and matching today's date,"
            " to this directory and then run this script again.\n- (If you need"
            " instructions for generating a Canvas Provisioning report, run this"
            " command with the '--help' flag.)"
        )

        raise typer.Exit(1)
    else:
        CSV_FILES = Path(REPORTS).glob("*.csv")
        TODAYS_REPORTS = list(filter(lambda file: TODAY in file.name, CSV_FILES))

        if not len(TODAYS_REPORTS):
            error = typer.style(
                "- ERROR: A Canvas Provisioning (Courses) CSV report matching today's"
                " date was not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                f"{error}\n- Please add a Canvas (Courses) Provisioning report for at"
                " least one term, matching today's date, to the following directory"
                f" and then run this script again: {colorize_path(str(REPORTS))}\n- (If"
                " you need instructions for generating a Canvas Provisioning report,"
                " run this command with the '--help' flag.)"
            )

            raise typer.Exit(1)
        else:
            total = len(TODAYS_REPORTS)
            if total == 1:
                report = "report"
            else:
                report = "reports"

            typer.echo(f"- Found {total} {report}:")

            FOUND_PATHS = list()

            for path in TODAYS_REPORTS:
                path = typer.style(path.stem, fg=typer.colors.GREEN)
                FOUND_PATHS.append(path)

            for path in FOUND_PATHS:
                typer.echo(f"- {path}")

            return TODAYS_REPORTS, report


def cleanup_report(reports, report_display, start=0):
    typer.echo(f") Preparing {report_display}...")

    data_frames = list()

    for report in reports:
        data = pandas.read_csv(report)
        data = data[
            [
                "canvas_course_id",
                "course_id",
                "canvas_account_id",
                "term_id",
                "status",
            ]
        ]
        data.drop_duplicates(inplace=True)
        data = data.astype("string", copy=False)
        data_frames.append(data)

    data_frame = pandas.concat(data_frames, ignore_index=True)

    TOTAL = len(data_frame.index)
    data_frame = data_frame.loc[start:TOTAL, :]

    return data_frame, str(TOTAL)


def process_result(tool):
    result = pandas.read_csv(RESULT_PATH)
    ACTIVE = result[result["found"] == "active"]
    INACTIVE = result[result["found"] == "inactive"]
    NOT_FOUND = result[result["found"] == "not found"]
    ERROR = result[
        (result["found"] != "active")
        & (result["found"] != "inactive")
        & (result["found"] != "not found")
    ]
    ACTIVE_COUNT = str(len(ACTIVE))
    INACTIVE_COUNT = str(len(INACTIVE))
    NOT_FOUND_COUNT = str(len(NOT_FOUND))
    ERROR_COUNT = str(len(ERROR))
    result = result[(result["found"] != "inactive") & (result["found"] != "not found")]
    result = result[["course_id", "term_id", "canvas_account_id"]]
    result = result.sort_values(by=["canvas_account_id"])

    with open(RESULT_PATH, "w", newline="") as result_file:
        writer(result_file).writerow(
            [f'COURSES WITH "{tool.upper()}" ENABLED', None, None]
        )

    result.to_csv(RESULT_PATH, mode="a", index=False)

    return ACTIVE_COUNT, INACTIVE_COUNT, NOT_FOUND_COUNT, ERROR_COUNT


def print_messages(tool, active, inactive, not_found, error, total):
    typer.secho("SUMMARY:", fg=typer.colors.YELLOW)
    typer.echo(f"- Processed {colorize(total)} courses.")
    typer.echo(f"- Found {colorize(active)} courses with {tool} enabled.")
    typer.echo(f"- Found {colorize(inactive)} courses with inactive {tool} tab.")
    typer.echo(f"- Found {colorize(not_found)} courses with no {tool} tab.")

    if int(error) > 0:
        message = typer.style(
            f"Encountered errors for {error} courses.",
            fg=typer.colors.RED,
        )
        typer.echo(f"- {message}")
        typer.echo(f"- Details recorded to result file: {RESULT_PATH}")

    typer.secho("FINISHED", fg=typer.colors.YELLOW)


def tool_main(tool, test, verbose, force):
    def check_tool_usage(course, canvas, verbose):
        try:
            (
                index,
                canvas_course_id,
                course_id,
                canvas_account_id,
                term_id,
                status,
            ) = course

            found = "not found"

            if not pandas.isna(course_id) and status == "active":
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()
                tool_tab = next(filter(lambda tab: tab.label == tool, tabs), None)

                if tool_tab and tool_tab.visibility == "public":
                    account = canvas.get_account(canvas_account_id)
                    school = account.name
                    found = "active"

                    if verbose:
                        found_display = typer.style(
                            found.upper(), fg=typer.colors.GREEN
                        )
                        typer.echo(
                            f'- ({index + 1}/{TOTAL}) "{tool}" {found_display}: {course_id}, {canvas_account_id} ({school})'
                        )
                else:
                    found = "inactive"
                    found_display = typer.style(found.upper(), fg=typer.colors.RED)
                    typer.echo(
                        f'- ({index + 1}/{TOTAL}) "{tool}" {found_display} for {course_id}.'
                    )
            elif verbose:
                found_display = typer.style(found.upper(), fg=typer.colors.RED)
                typer.echo(
                    f'- ({index + 1}/{TOTAL}) "{tool}" {found_display} for {course_id}.'
                )
        except Exception as error:
            if verbose:
                message = typer.style(f"ERROR: Failed to process {course_id} ({error})")
                typer.echo(f"- ({index + 1}/{TOTAL}) {message}")
            found = f"{str(error)}"

        report.at[index, "found"] = found
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

    REPORTS, report_display = find_course_report()
    START = get_start_index(force, RESULT_PATH)
    report, TOTAL = cleanup_report(REPORTS, report_display, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    typer.echo(") Processing courses...")

    toggle_progress_bar(report, check_tool_usage, CANVAS, verbose, index=True)
    active, inactive, not_found, error = process_result(tool)
    print_messages(tool, active, inactive, not_found, error, TOTAL)
