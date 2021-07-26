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
REPORTS, RESULTS, PROCESSED = get_command_paths("tool", processed=True)
HEADERS = [
    "index",
    "canvas_course_id",
    "course_id",
    "short_name",
    "long_name",
    "canvas_account_id",
    "term_id",
    "status",
    "tool status",
]

RESERVE_ACCOUNTS = [
    "99243",
    "128877",
    "99244",
    "99239",
    "99242",
    "99237",
    "99238",
    "99240",
]


def check_tool(tool):
    if tool.lower() == "reserve" or tool == "reserves":
        return "Course Materials @ Penn Libraries"
    else:
        return tool


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
                "short_name",
                "long_name",
                "canvas_account_id",
                "term_id",
                "status",
            ]
        ]
        data.drop_duplicates(inplace=True)
        data = data.astype("string", copy=False, errors="ignore")
        data_frames.append(data)

    data_frame = pandas.concat(data_frames, ignore_index=True)

    TOTAL = len(data_frame.index)
    data_frame = data_frame.loc[start:TOTAL, :]

    return data_frame, str(TOTAL)


def get_processed_courses(processed_path):
    typer.echo(") Finding courses already processed...")

    if processed_path.is_file():
        result = pandas.read_csv(processed_path)
        result = result.astype("string", copy=False, errors="ignore")
        return result["canvas_course_id"].tolist()
    else:
        make_csv_paths(PROCESSED, processed_path, ["canvas_course_id"])
        return list()


def process_result(tool, enable, result_path):
    result = pandas.read_csv(result_path)
    ENABLED = result[result["tool status"] == "enabled"]
    ALREADY_ENABLED = result[result["tool status"] == "already enabled"]
    DISABLED = result[result["tool status"] == "disabled"]
    NOT_FOUND = result[result["tool status"] == "not found"]
    NOT_PARTICIPATING = result[result["tool status"] == "school not participating"]
    ERROR = result[
        (result["tool status"] != "enabled")
        & (result["tool status"] != "already enabled")
        & (result["tool status"] != "disabled")
        & (result["tool status"] != "not found")
        & (result["tool status"] != "school not participating")
    ]
    ENABLED_COUNT = len(ENABLED)
    ALREADY_ENABLED_COUNT = len(ALREADY_ENABLED)
    DISABLED_COUNT = str(len(DISABLED))
    NOT_FOUND_COUNT = str(len(NOT_FOUND))
    NOT_PARTICIPATING_COUNT = str(len(NOT_PARTICIPATING))
    ERROR_COUNT = len(ERROR)

    if ERROR_COUNT:
        result = result[
            (result["tool status"] != "disabled")
            & (result["tool status"] != "not found")
            & (result["tool status"] != "school not participating")
        ]

        if enable:
            result = result[(result["tool status"] != "already enabled")]

        status_values_to_clear = ["already enabled", "enabled"]
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
    elif enable:
        result = result[result["tool status"] == "enabled"]
    else:
        result = result[result["tool status"] == "already enabled"]

    if ERROR_COUNT:
        result = result[["canvas_account_id", "term_id", "course_id", "error"]]
    else:
        result = result[["canvas_account_id", "term_id", "course_id"]]

    result = result.groupby(["canvas_account_id", "term_id"], group_keys=False).apply(
        pandas.DataFrame.sort_values, "course_id"
    )
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
            if enable:
                writer(result_file).writerow(
                    [f'"{tool.upper()}" NOT ENABLED FOR ANY COURSES']
                )
            else:
                writer(result_file).writerow(
                    [f'NO COURSES WITH "{tool.upper()}" ENABLED']
                )
    else:
        with open(result_path, "w", newline="") as result_file:
            if enable:
                writer(result_file).writerow(
                    [f'ENABLED "{tool.upper()}" FOR COURSES', None, None]
                )
            else:
                writer(result_file).writerow(
                    [f'COURSES WITH "{tool.upper()}" ENABLED', None, None]
                )

        result.to_csv(result_path, mode="a", index=False)

    return (
        str(ENABLED_COUNT),
        str(ALREADY_ENABLED_COUNT),
        DISABLED_COUNT,
        NOT_FOUND_COUNT,
        NOT_PARTICIPATING_COUNT,
        str(ERROR_COUNT),
    )


def print_messages(
    tool,
    enable,
    enabled,
    already_enabled,
    disabled,
    not_found,
    not_participating,
    error,
    total,
    result_path,
):
    tool = typer.style(tool, fg=typer.colors.CYAN)
    typer.secho("SUMMARY:", fg=typer.colors.YELLOW)
    typer.echo(f"- Processed {colorize(total)} courses.")
    total_enabled = typer.style(enabled, fg=typer.colors.GREEN)
    total_already_enabled = typer.style(already_enabled, fg=typer.colors.GREEN)

    if enable:
        typer.echo(f'- Enabled "{tool}" for {total_enabled} courses.')
        if int(total_already_enabled):
            typer.echo(
                f'- Found {total_already_enabled} courses with "{tool}" already'
                " enabled."
            )
    else:
        typer.echo(f'- Found {total_already_enabled} courses with "{tool}" enabled.')
        typer.echo(f'- Found {colorize(disabled)} courses with disabled "{tool}" tab.')

    if int(not_found):
        message = typer.style(not_found, fg=typer.colors.YELLOW)
        typer.echo(f'- Found {message} courses with no "{tool}" tab.')

    if int(not_participating):
        message = typer.style(not_participating, fg=typer.colors.YELLOW)
        typer.echo(
            f"- Found {message} courses in schools not participating in automatic"
            f' enabling of "{tool}".'
        )

    if int(error):
        message = typer.style(
            f"Encountered errors for {error} courses.",
            fg=typer.colors.RED,
        )
        typer.echo(f"- {message}")
        result_path_display = typer.style(str(result_path), fg=typer.colors.GREEN)
        typer.echo(f"- Details recorded to result file: {result_path_display}")

    typer.secho("FINISHED", fg=typer.colors.YELLOW)


def tool_main(tool, use_id, enable, test, verbose, force):
    def check_tool_usage(course, canvas, verbose, args):
        if len(args) == 4:
            tool, use_id, enable, PROCESSED_COURSES = args
        else:
            tool, use_id, enable = args

        tool_display = typer.style(tool, fg=typer.colors.CYAN)
        (
            index,
            canvas_course_id,
            course_id,
            short_name,
            long_name,
            canvas_account_id,
            term_id,
            status,
        ) = course

        tool_status = "not found"
        error = False

        if enable and canvas_course_id in PROCESSED_COURSES:
            tool_status = "already processed"
            found_display = typer.style(tool_status.upper(), fg=typer.colors.YELLOW)
        elif (
            enable
            and tool == "Course Materials @ Penn Libraries"
            and canvas_account_id not in RESERVE_ACCOUNTS
        ):
            tool_status = "school not participating"
            found_display = typer.style(
                f"NOT ENABLED ({tool_status.upper()})", fg=typer.colors.YELLOW
            )
        elif not enable and status != "active" and verbose:
            found_display = typer.style(tool_status.upper(), fg=typer.colors.YELLOW)
        else:
            try:
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()

                if use_id:
                    tool_tab = next(filter(lambda tab: tab.id == tool, tabs), None)
                else:
                    tool_tab = next(filter(lambda tab: tab.label == tool, tabs), None)

                if not tool_tab:
                    found_display = typer.style(
                        tool_status.upper(), fg=typer.colors.YELLOW
                    )
                elif tool_tab.visibility == "public":
                    tool_status = "already enabled"

                    if verbose:
                        if enable:
                            found_display = typer.style(
                                tool_status.upper(), fg=typer.colors.YELLOW
                            )
                        else:
                            found_display = typer.style(
                                "ENABLED", fg=typer.colors.GREEN
                            )
                elif enable:
                    tool_tab.update(hidden=False, position=3)
                    tool_status = "enabled"

                    if verbose:
                        found_display = typer.style(
                            tool_status.upper(), fg=typer.colors.GREEN
                        )
                else:
                    tool_status = "disabled"

                    if verbose:
                        found_display = typer.style(
                            tool_status.upper(), fg=typer.colors.YELLOW
                        )
            except Exception as error_message:
                tool_status = f"{str(error_message)}"
                error = True

                if verbose:
                    message = typer.style(
                        f"ERROR: Failed to process {course_id} ({error_message})"
                    )
                    typer.echo(f"- ({index + 1}/{TOTAL}) {message}")

        if verbose and not error:
            if pandas.isna(course_id):
                course_display = f"{long_name} ({canvas_course_id})"
            else:
                course_display = f"{course_id}"

            typer.echo(
                f'- ({index + 1}/{TOTAL}) "{tool_display}" {found_display} for'
                f" {course_display}."
            )

        if pandas.isna(course_id):
            report.at[index, "course_id"] = f"{short_name} ({canvas_account_id})"

        report.at[index, "tool status"] = tool_status
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if tool_status != "already processed":
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id])

    tool = check_tool(tool)
    REPORTS, report_display = find_course_report()
    RESULT_PATH = (
        RESULTS
        / f"{TODAY_AS_Y_M_D}_{tool.replace(' ', '_')}_tool_{'enable' if enable else 'report'}_result.csv"
    )
    START = get_start_index(force, RESULT_PATH)

    if enable:
        PROCESSED_PATH = (
            PROCESSED / f"{tool.replace(' ', '_')}_tool_enable_processed_courses.csv"
        )
        PROCESSED_COURSES = get_processed_courses(PROCESSED_PATH)

    report, TOTAL = cleanup_report(REPORTS, report_display, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    tool_display = typer.style(tool, fg=typer.colors.CYAN)

    if enable:
        if tool == "Course Materials @ Penn Libraries":
            ACCOUNTS_DISPLAY = map(
                lambda account: typer.style(account, fg=typer.colors.MAGENTA),
                RESERVE_ACCOUNTS,
            )
            ACCOUNTS = f"{', '.join(ACCOUNTS_DISPLAY)}"
            typer.echo(f') Enabling "{tool_display}" for courses in {ACCOUNTS}...')
        else:
            typer.echo(f') Enabling "{tool_display}" for courses...')
    else:
        typer.echo(f') Checking courses for "{tool_display}"...')

    if enable:
        ARGS = (tool, use_id, enable, PROCESSED_COURSES)
    else:
        ARGS = (tool, use_id, enable)

    toggle_progress_bar(
        report,
        check_tool_usage,
        CANVAS,
        verbose,
        args=ARGS,
        index=True,
    )
    (
        enabled,
        already_enabled,
        disabled,
        not_found,
        not_participating,
        error,
    ) = process_result(tool, enable, RESULT_PATH)
    print_messages(
        tool,
        enable,
        enabled,
        already_enabled,
        disabled,
        not_found,
        not_participating,
        error,
        TOTAL,
        RESULT_PATH,
    )
