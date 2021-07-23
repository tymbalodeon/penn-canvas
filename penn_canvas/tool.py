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
HEADERS = [
    "index",
    "canvas_course_id",
    "course_id",
    "canvas_account_id",
    "term_id",
    "status",
    "tool status",
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
            " Please add a Canvas Provisioning (Courses) report for at least one term,"
            " and matching today's date, to this directory and then run this script"
            " again.\n- (If you need instructions for generating a Canvas Provisioning"
            " report, run this command with the '--help' flag.)"
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


def process_result(tool, result_path):
    result = pandas.read_csv(result_path)
    ENABLED = result[result["tool status"] == "enabled"]
    DISABLED = result[result["tool status"] == "disabled"]
    NOT_FOUND = result[result["tool status"] == "not found"]
    ERROR = result[
        (result["tool status"] != "enabled")
        & (result["tool status"] != "disabled")
        & (result["tool status"] != "not found")
    ]
    ENABLED_COUNT = len(ENABLED)
    DISABLED_COUNT = str(len(DISABLED))
    NOT_FOUND_COUNT = str(len(NOT_FOUND))
    ERROR_COUNT = len(ERROR)

    if ERROR_COUNT:
        result = result[
            (result["tool status"] != "disabled")
            & (result["tool status"] != "not found")
        ]
        result = result[["canvas_account_id", "term_id", "course_id", "tool status"]]
        status_values_to_clear = ["enabled", "disabled", "not found"]
        result["tool status"] = result["tool status"].apply(
            lambda tool_status: None
            if tool_status in status_values_to_clear
            else tool_status
        )
        result.rename(
            columns={
                "tool status": "error",
            },
            inplace=True,
        )
    elif ENABLED_COUNT:
        result = result[result["tool status"] == "enabled"]
        result = result[["canvas_account_id", "term_id", "course_id"]]

    if ERROR_COUNT or ENABLED_COUNT:
        result = result.groupby(
            ["canvas_account_id", "term_id"], group_keys=False
        ).apply(pandas.DataFrame.sort_values, "course_id")
        result.rename(
            columns={
                "canvas_account_id": "canvas account id",
                "term_id": "term id",
                "course_id": "course id",
            },
            inplace=True,
        )

    if result.empty:
        with open(result_path, "w", newline="") as result_file:
            writer(result_file).writerow([f'NO COURSES WITH "{tool.upper()}" ENABLED'])
    else:
        with open(result_path, "w", newline="") as result_file:
            writer(result_file).writerow(
                [f'COURSES WITH "{tool.upper()}" ENABLED', None, None]
            )
        result.to_csv(result_path, mode="a", index=False)

    return str(ENABLED_COUNT), DISABLED_COUNT, NOT_FOUND_COUNT, str(ERROR_COUNT)


def print_messages(tool, enabled, disabled, not_found, error, total, result_path):
    tool = typer.style(tool, fg=typer.colors.CYAN)
    typer.secho("SUMMARY:", fg=typer.colors.YELLOW)
    typer.echo(f"- Processed {colorize(total)} courses.")
    total_enabled = typer.style(enabled, fg=typer.colors.GREEN)
    typer.echo(f'- Found {total_enabled} courses with "{tool}" enabled.')
    typer.echo(f'- Found {colorize(disabled)} courses with disabled "{tool}" tab.')
    typer.echo(f'- Found {colorize(not_found)} courses with no "{tool}" tab.')

    if int(error) > 0:
        message = typer.style(
            f"Encountered errors for {error} courses.",
            fg=typer.colors.RED,
        )
        typer.echo(f"- {message}")
        result_path_display = typer.style(result_path, fg=typer.colors.GREEN)
        typer.echo(f"- Details recorded to result file: {result_path_display}")

    typer.secho("FINISHED", fg=typer.colors.YELLOW)


def tool_main(tool, use_id, test, verbose, force):
    def check_tool_usage(course, canvas, verbose, args):
        tool = args[0]
        use_id = args[1]
        tool_display = typer.style(tool, fg=typer.colors.CYAN)

        try:
            (
                index,
                canvas_course_id,
                course_id,
                canvas_account_id,
                term_id,
                status,
            ) = course

            tool_status = "not found"

            if not pandas.isna(course_id) and status == "active":
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()

                if use_id:
                    tool_tab = next(filter(lambda tab: tab.id == tool, tabs), None)
                else:
                    tool_tab = next(filter(lambda tab: tab.label == tool, tabs), None)

                if tool_tab:
                    if tool_tab.visibility == "public":
                        tool_status = "enabled"

                        if verbose:
                            found_display = typer.style(
                                tool_status.upper(), fg=typer.colors.GREEN
                            )
                            typer.echo(
                                f'- ({index + 1}/{TOTAL}) "{tool_display}"'
                                f" {found_display}: {course_id},"
                                f" {canvas_account_id}"
                            )
                    else:
                        tool_status = "disabled"

                        if verbose:
                            found_display = typer.style(
                                tool_status.upper(), fg=typer.colors.YELLOW
                            )
                            typer.echo(
                                f'- ({index + 1}/{TOTAL}) "{tool_display}"'
                                f" {found_display} for {course_id}."
                            )
                else:
                    found_display = typer.style(
                        tool_status.upper(), fg=typer.colors.YELLOW
                    )
                    typer.echo(
                        f'- ({index + 1}/{TOTAL}) "{tool_display}" {found_display} for'
                        f" {course_id}."
                    )
            elif verbose:
                found_display = typer.style(tool_status.upper(), fg=typer.colors.YELLOW)
                typer.echo(
                    f'- ({index + 1}/{TOTAL}) "{tool_display}" {found_display} for'
                    f" {course_id}."
                )
        except Exception as error:
            if verbose:
                message = typer.style(f"ERROR: Failed to process {course_id} ({error})")
                typer.echo(f"- ({index + 1}/{TOTAL}) {message}")
            tool_status = f"{str(error)}"

        report.at[index, "tool status"] = tool_status
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

    REPORTS, report_display = find_course_report()
    RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_{tool}_tool_result.csv"
    START = get_start_index(force, RESULT_PATH)
    report, TOTAL = cleanup_report(REPORTS, report_display, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    typer.echo(") Processing courses...")

    toggle_progress_bar(
        report, check_tool_usage, CANVAS, verbose, args=[tool, use_id], index=True
    )
    enabled, disabled, not_found, error = process_result(tool, RESULT_PATH)
    print_messages(tool, enabled, disabled, not_found, error, TOTAL, RESULT_PATH)
