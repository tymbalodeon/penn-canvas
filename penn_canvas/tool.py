from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path

from pandas import DataFrame, concat, isna, read_csv
from typer import Exit, confirm, echo

from .helpers import (
    TODAY,
    TODAY_AS_Y_M_D,
    YEAR,
    colorize,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    handle_clear_processed,
    get_processed,
    make_skip_message,
    toggle_progress_bar,
)

REPORTS, RESULTS, PROCESSED = get_command_paths("tool", processed=True)
HEADERS = [
    "index",
    "canvas course id",
    "course id",
    "short name",
    "long name",
    "canvas account id",
    "term id",
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


def get_account_names(accounts, canvas):
    return [
        account.name
        for account in [canvas.get_account(account) for account in accounts]
    ]


def check_tool(tool):
    if tool.lower() in {"reserve", "reserves"}:
        return "Course Materials @ Penn Libraries"
    else:
        return tool


def find_course_report(enable):
    echo(") Finding Canvas Provisioning (Courses) report(s)...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = colorize("- ERROR: Canvas tool reports directory not found.", "yellow")
        echo(
            f"{error} \n- Creating one for you at: {colorize(REPORTS, 'green')}\n-"
            " Please add a Canvas Provisioning (Courses) report for at least one term,"
            " and matching today's date, to this directory and then run this script"
            " again.\n- (If you need instructions for generating a Canvas Provisioning"
            " report, run this command with the '--help' flag.)"
        )

        raise Exit(1)
    else:
        CSV_FILES = [report for report in Path(REPORTS).glob("*.csv")]
        TODAYS_REPORTS = [report for report in CSV_FILES if TODAY in report.name]

        if not len(TODAYS_REPORTS):
            error = colorize(
                "- ERROR: A Canvas Provisioning (Courses) CSV report matching today's"
                " date was not found.",
                "yellow",
            )
            echo(
                f"{error}\n- Please add a Canvas (Courses) Provisioning report for at"
                " least one term, matching today's date, to the following directory"
                f" and then run this script again: {colorize(REPORTS, 'green')}\n- (If"
                " you need instructions for generating a Canvas Provisioning report,"
                " run this command with the '--help' flag.)"
            )

            raise Exit(1)
        else:
            total = len(TODAYS_REPORTS)

            if total == 1:
                report_display = "report"
            else:
                report_display = "reports"

            if not enable:
                echo(f"- Found {total} {report_display}:")

                FOUND_PATHS = list()

                for path in TODAYS_REPORTS:
                    FOUND_PATHS.append(colorize(path.stem, "green"))

                for path in FOUND_PATHS:
                    echo(f"- {path}")

            return TODAYS_REPORTS, report_display


def cleanup_reports(
    reports,
    report_display,
    enable,
    processed_courses=None,
    processed_errors=None,
    new=False,
    start=0,
):
    echo(f") Preparing {report_display}...")

    def cleanup_report(report):
        data = read_csv(report)
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
        data.sort_values("course_id", inplace=True, ignore_index=True)
        data = data.astype("string", copy=False, errors="ignore")

        if enable:
            data = data[~data["canvas_course_id"].isin(processed_courses)]

        return data

    if enable:
        data_frame = cleanup_report(reports[0])
        data_frame.reset_index(drop=True, inplace=True)
        already_processed_count = len(processed_courses)

        if new:
            data_frame = data_frame[
                ~data_frame["canvas_course_id"].isin(processed_errors)
            ]
            already_processed_count = already_processed_count + len(processed_errors)

        if already_processed_count:
            message = colorize(
                f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
                f" {'COURSE' if already_processed_count == 1 else 'COURSES'}...",
                "yellow",
            )
            echo(f") {message}")
    else:
        data_frames = list()

        for report in reports:
            data = cleanup_report(report)
            data_frames.append(data)

        data_frame = concat(data_frames, ignore_index=True)

    total = len(data_frame.index)
    data_frame = data_frame.loc[start:total, :]
    data_frame["term_id"].fillna("N/A", inplace=True)
    terms = data_frame["term_id"].drop_duplicates().tolist()

    return data_frame, f"{total:,}", terms


def process_result(tool, terms, enable, result_path):
    result = read_csv(result_path)
    enabled = result[result["tool status"] == "enabled"]
    already_enabled = result[result["tool status"] == "already enabled"]
    disabled = result[result["tool status"] == "disabled"]
    not_found = result[result["tool status"] == "not found"]
    unsupported = result[result["tool status"] == "unsupported"]
    error = result[
        (result["tool status"] != "enabled")
        & (result["tool status"] != "already enabled")
        & (result["tool status"] != "disabled")
        & (result["tool status"] != "not found")
        & (result["tool status"] != "unsupported")
    ]

    enabled_count = len(enabled)
    already_enabled_count = len(already_enabled)
    disabled_count = len(disabled)
    not_found_count = len(not_found)
    unsupported_count = len(unsupported)
    error_count = len(error)

    if enable:
        enabled_path = RESULTS / f"{result_path.stem}_ENABLED.csv"
        enabled = enabled[["canvas course id", "course id"]]
        enabled.to_csv(enabled_path, index=False)
        error_result = concat([error, not_found])
        error_result = error_result[["canvas course id", "course id"]]
        error_path = RESULTS / f"{result_path.stem}_ERROR.csv"
        error_result.to_csv(error_path, index=False)
    else:
        result = concat([enabled, not_found, error])

        if error_count:
            result["tool status"] = result["tool status"].apply(
                lambda tool_status: None if tool_status == "enabled" else tool_status
            )
            result.rename(
                columns={
                    "tool status": "error",
                },
                inplace=True,
            )
            result = result[["term id", "canvas course id", "course id", "error"]]
        else:
            result = result[["term id", "canvas course id", "course id"]]

        result = result.groupby(
            ["canvas course id", "term id"], group_keys=False
        ).apply(DataFrame.sort_values, "course id")
        final_path = (
            RESULTS / f"{'_'.join(terms).replace('/', '')}_{result_path.stem}.csv"
        )
        result.to_csv(final_path, index=False)

    remove(result_path)

    return (
        enabled_count,
        already_enabled_count,
        disabled_count,
        not_found_count,
        unsupported_count,
        error_count,
        result_path,
    )


def print_messages(
    tool,
    enable,
    enabled,
    already_enabled,
    disabled,
    not_found,
    not_supported,
    error,
    total,
    result_path,
):
    tool = colorize(tool, "blue")
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} courses.")
    total_enabled = colorize(enabled, "green" if enabled else "yellow")
    total_already_enabled = colorize(already_enabled, "cyan")

    if enable:
        echo(f'- Enabled "{tool}" for {total_enabled} courses.')

        if already_enabled:
            echo(
                f'- Found {total_already_enabled} courses with "{tool}" already'
                " enabled."
            )
    else:
        echo(f'- Found {total_enabled} courses with "{tool}" enabled.')
        echo(
            f'- Found {colorize(disabled, "yellow")} courses with disabled "{tool}"'
            " tab."
        )

    if not_found:
        message = colorize(not_found, "yellow")
        echo(f'- Found {message} courses with no "{tool}" tab.')

    if not_supported:
        message = colorize(not_supported, "yellow")
        echo(
            f"- Found {message} courses in schools not participating in automatic"
            f' enabling of "{tool}".'
        )

    if error:
        message = colorize(f"Encountered errors for {error:,} courses.", "red")
        echo(f"- {message}")
        result_path_display = colorize(result_path, "green")
        echo(f"- Details recorded to result file: {result_path_display}")

    colorize("FINISHED", "yellow", True)


def tool_main(tool, use_id, enable, test, verbose, new, force, clear_processed):
    def check_tool_usage(course, canvas, verbose, args):
        if len(args) == 4:
            tool, use_id, enable, PROCESSED_COURSES = args
        else:
            tool, use_id, enable = args

        tool_display = colorize(tool, "blue")
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

        if (
            enable
            and tool == "Course Materials @ Penn Libraries"
            and canvas_account_id not in RESERVE_ACCOUNTS
        ):
            tool_status = "unsupported"
        else:
            try:
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()

                if use_id:
                    tool_tab = next((tab for tab in tabs if tab.id == tool), None)
                else:
                    tool_tab = next((tab for tab in tabs if tab.label == tool), None)

                if tool_tab and tool_tab.visibility == "public":
                    tool_status = "already enabled" if enable else "enabled"
                elif enable:
                    tool_tab.update(hidden=False, position=3)
                    tool_status = "enabled"
                else:
                    tool_status = "disabled"
            except Exception as error_message:
                tool_status = f"{str(error_message)}"
                error = True

                if verbose:
                    message = colorize(
                        f"ERROR: Failed to process {course_id} ({error_message})", "red"
                    )
                    echo(f"- ({(index + 1):,}/{total}) {message}")

        if verbose and not error:
            if isna(course_id):
                course_display = f"{long_name} ({canvas_course_id})"
            else:
                course_display = f"{course_id}"

            color = PRINT_COLOR_MAPS.get(tool_status)
            found_display = colorize(tool_status.upper(), color)
            echo(
                f'- ({(index + 1):,}/{total}) "{tool_display}" {found_display} for'
                f" {course_display}."
            )

        if isna(course_id):
            report.at[index, "course_id"] = f"{short_name} ({canvas_account_id})"

        report.at[index, "tool status"] = tool_status
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if enable and tool_status in {"already enabled", "enabled", "unsupported"}:
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id])
        elif enable and canvas_course_id not in PROCESSED_ERRORS:
            if canvas_course_id in PROCESSED_ERRORS:
                processed_errors_csv = read_csv(PROCESSED_ERRORS_PATH)
                rocessed_errors_csv = processed_errors_csv[
                    processed_errors_csv["canvas user id"] != canvas_course_id
                ]
                processed_errors_csv.to_csv(PROCESSED_ERRORS_PATH, index=False)

            with open(PROCESSED_ERRORS_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id])

    tool = check_tool(tool)
    REPORTS, report_display = find_course_report(enable)
    RESULT_FILE_NAME = (
        f"{f'{YEAR}_' if enable else ''}{tool.replace(' ', '_')}"
        f"{'' if enable else 'REPORT'}"
        f"{'_test' if test else ''}.csv"
    )
    RESULT_PATH = RESULTS / RESULT_FILE_NAME
    START = get_start_index(force, RESULT_PATH)

    if enable:
        PROCESSED_STEM = (
            f"{tool.replace(' ', '_')}_tool_enable_processed_courses"
            f"{'_test' if test else ''}.csv"
        )
        PROCESSED_PATH = PROCESSED / PROCESSED_STEM
        PROCESSED_ERRORS_STEM = (
            f"{tool.replace(' ', '_')}_tool_enable_processed_errors"
            f"{'_test' if test else ''}.csv"
        )
        PROCESSED_ERRORS_PATH = PROCESSED / PROCESSED_ERRORS_STEM
        handle_clear_processed(
            clear_processed, [PROCESSED_PATH, PROCESSED_ERRORS_PATH], "courses"
        )
        PROCESSED_COURSES = get_processed(PROCESSED, PROCESSED_PATH, "canvas course id")
        PROCESSED_ERRORS = get_processed(
            PROCESSED, PROCESSED_ERRORS_PATH, "canvas course id"
        )

    report, total, terms = cleanup_reports(
        REPORTS,
        report_display,
        enable,
        PROCESSED_COURSES if enable else None,
        PROCESSED_ERRORS if enable else None,
        new if enable else False,
        START,
    )

    if not force and not enable:
        PREVIOUS_RESULTS = [result_file for result_file in Path(RESULTS).glob("*.csv")]
        PREVIOUS_RESULTS_FOR_TERM = dict()

        for term in terms:
            for result_file in PREVIOUS_RESULTS:
                if term in result_file.name:
                    PREVIOUS_RESULTS_FOR_TERM[term] = result_file

        TERMS_TO_RUN = list()

        for term in PREVIOUS_RESULTS_FOR_TERM:
            path_display = colorize(PREVIOUS_RESULTS_FOR_TERM[term], "green")
            message = colorize(
                f"REPORT FOR {tool.upper()} HAS ALREADY BEEN GENERATED FOR TERM"
                f" {term.upper()}: {path_display}",
                "yellow",
            )
            echo(f"- {message}")
            run_again = confirm(
                f"Would you like to generate a report for term {term} again?"
            )
            if not run_again:
                TERMS_TO_RUN.append(term)

        if len(TERMS_TO_RUN):
            for term in TERMS_TO_RUN:
                report = report[report["term_id"] != term]

            report.reset_index(inplace=True)
            report.drop(["index"], axis=1, inplace=True)
            total = f"{len(report.index):,}"
            terms = report["term_id"].drop_duplicates().tolist()

            if not terms:
                echo("NO NEW TERMS TO PROCESS")
                colorize("FINISHED", "yellow", True)

                raise Exit()

    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    tool_display = colorize(tool, "blue")
    TERMS_DISPLAY = [colorize(term, "yellow") for term in terms]
    STYLED_TERMS = f"{', '.join(TERMS_DISPLAY)}"

    if enable:
        if tool == "Course Materials @ Penn Libraries":
            ACCOUNTS_DISPLAY = [
                colorize(f"\n\t* {account}", "magenta")
                for account in get_account_names(RESERVE_ACCOUNTS, CANVAS)
            ]
            ACCOUNTS = f"{''.join(ACCOUNTS_DISPLAY)}"
            echo(
                f') Enabling "{tool_display}" for {STYLED_TERMS} courses in: {ACCOUNTS}'
            )
        else:
            echo(f') Enabling "{tool_display}" for {STYLED_TERMS} courses...')
    else:
        echo(f') Checking {STYLED_TERMS} courses for "{tool_display}"...')

    if enable:
        ARGS = (tool, use_id, enable, PROCESSED_COURSES)
    else:
        ARGS = (tool, use_id, enable)

    if verbose:
        PRINT_COLOR_MAPS = {
            "not found": "red",
            "already processed": "yellow",
            "unsupported": "yellow",
            "already enabled": "cyan",
            "enabled": "green",
            "disabled": "yellow",
        }

    toggle_progress_bar(report, check_tool_usage, CANVAS, verbose, args=ARGS)
    (
        enabled,
        already_enabled,
        disabled,
        not_found,
        not_participating,
        error,
        result_path,
    ) = process_result(tool, terms, enable, RESULT_PATH)
    print_messages(
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
    )
