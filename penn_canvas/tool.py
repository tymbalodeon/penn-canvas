from csv import writer
from os import remove
from pathlib import Path

from pandas import DataFrame, concat, isna, read_csv
from typer import Exit, confirm, echo

from penn_canvas.report import get_report
from penn_canvas.style import print_item

from .helpers import (
    BASE_PATH,
    YEAR,
    add_headers_to_empty_files,
    color,
    create_directory,
    drop_duplicate_errors,
    dynamic_to_csv,
    get_account,
    get_canvas,
    get_processed,
    get_start_index,
    handle_clear_processed,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    toggle_progress_bar,
)

COMMAND_PATH = create_directory(BASE_PATH / "Tool")
PROCESSED = COMMAND_PATH / ".processed"
INPUT_FILE_NAME = "Canvas Provisioning (Courses) report"
HEADERS = [
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


def get_account_names(accounts):
    return [get_account(account).name for account in accounts]


def get_tool(tool):
    tool = tool.lower()
    if tool in {"reserve", "reserves"}:
        return "Course Materials @ Penn Libraries"
    elif tool == "panopto":
        return "Class Recordings"
    else:
        return tool


def process_report(
    report_path,
    start,
    enable,
    processed_courses,
    processed_errors,
    new,
    account_id,
):
    report = read_csv(report_path)
    report = report[
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
    report.drop_duplicates(inplace=True)
    report.sort_values("course_id", inplace=True, ignore_index=True)
    report = report.astype("string", copy=False, errors="ignore")
    if account_id:
        report = report[report["canvas_account_id"] == account_id]
    if enable:
        report = report[~report["canvas_course_id"].isin(processed_courses)]
        report.reset_index(drop=True, inplace=True)
        already_processed_count = len(processed_courses)
        if new:
            report = report[~report["canvas_course_id"].isin(processed_errors)]
            already_processed_count = already_processed_count + len(processed_errors)
        if already_processed_count:
            message = color(
                f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
                f" {'COURSE' if already_processed_count == 1 else 'COURSES'}...",
                "yellow",
            )
            echo(f") {message}")
        total = len(report.index)
        report = report.loc[start:total, :]
    else:
        total = len(report.index)
    report["term_id"].fillna("N/A", inplace=True)
    return report, total


def process_result(terms, enable, result_path, new):
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
    if enable:
        BASE = COMMAND_PATH / "Enabled" / YEAR
        if not BASE.exists():
            Path.mkdir(BASE, parents=True)
        enabled_path = BASE / f"{result_path.stem}_ENABLED.csv"
        enabled = enabled[["canvas course id", "course id"]]
        dynamic_to_csv(enabled_path, enabled, enabled_path.exists())
        error_result = concat([error, not_found])
        error_result.rename(
            columns={
                "tool status": "error",
            },
            inplace=True,
        )
        error_result = error_result[["canvas course id", "course id", "error"]]
        error_path = BASE / f"{result_path.stem}_ERROR.csv"
        dynamic_to_csv(error_path, error_result, new)
        if new:
            try:
                drop_duplicate_errors([error_path])
            except Exception:
                pass
        else:
            add_headers_to_empty_files(
                [enabled_path],
                ["canvas course id", "course id", "error"],
            )
    else:
        BASE = COMMAND_PATH / "Reports"
        if not BASE.exists():
            Path.mkdir(BASE)
        ENABLED_STEM = (
            f"{'_'.join(terms).replace('/', '')}_{result_path.stem}_REPORT_ENABLED.csv"
        )
        enabled_path = BASE / ENABLED_STEM
        enabled = enabled[
            ["term id", "canvas course id", "course id", "canvas account id"]
        ]
        enabled = enabled.groupby(
            ["canvas course id", "canvas account id", "term id"], group_keys=False
        ).apply(DataFrame.sort_values, "course id")
        enabled.to_csv(enabled_path, index=False)
        error_path = (
            BASE
            / f"{'_'.join(terms).replace('/', '')}_{result_path.stem}_REPORT_ERROR.csv"
        )
        error_result = concat([error, not_found])
        error_result.rename(
            columns={
                "tool status": "error",
            },
            inplace=True,
        )
        error_result = error_result[
            ["term id", "canvas course id", "course id", "error"]
        ]
        error_result = error_result.groupby(
            ["canvas course id", "term id"], group_keys=False
        ).apply(DataFrame.sort_values, "course id")

        if error_result.empty:
            with open(error_path, "w", newline="") as result:
                writer(result).writerow(
                    ["term id", "canvas course id", "course id", "error"]
                )
        else:
            error_result.to_csv(error_path, index=False)
    remove(result_path)
    return (
        len(enabled.index),
        len(already_enabled.index),
        len(disabled.index),
        len(not_found.index),
        len(unsupported.index),
        len(error.index),
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
    tool = color(tool, "blue")
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total, 'magenta')} courses.")
    total_enabled = color(enabled, "green" if enabled else "yellow")
    total_already_enabled = color(already_enabled, "cyan")
    if enable:
        echo(f'- Enabled "{tool}" for {total_enabled} courses.')
        if already_enabled:
            echo(
                f'- Found {total_already_enabled} courses with "{tool}" already'
                " enabled."
            )
    else:
        echo(f'- Found {total_enabled} courses with "{tool}" enabled.')
        echo(f'- Found {color(disabled, "yellow")} courses with disabled "{tool}" tab.')
    if not_found:
        message = color(not_found, "yellow")
        echo(f'- Found {message} courses with no "{tool}" tab.')
    if not_supported:
        message = color(not_supported, "yellow")
        echo(
            f"- Found {message} courses in schools not participating in automatic"
            f' enabling of "{tool}".'
        )
    if error:
        message = color(f"Encountered errors for {error:,} courses.", "red")
        echo(f"- {message}")
        result_path_display = color(result_path, "green")
        echo(f"- Details recorded to result file: {result_path_display}")
    color("FINISHED", "yellow", True)


def tool_main(
    tool,
    term,
    use_id,
    enable,
    test,
    verbose,
    new,
    force,
    force_report,
    clear_processed,
    account_id,
):
    def check_tool_usage(course, canvas, verbose, args):
        tool, use_id, enable = args
        tool_display = color(tool, "blue")
        (
            index,
            canvas_course_id,
            course_id,
            short_name,
            long_name,
            canvas_account_id,
        ) = course[:6]
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
                elif tool_tab and enable:
                    tool_tab.update(hidden=False, position=3)
                    tool_status = "enabled"
                else:
                    tool_status = "disabled"
            except Exception as error_message:
                tool_status = f"{str(error_message)}"
                error = True
                if verbose:
                    message = color(
                        f"ERROR: Failed to process {course_id} ({error_message})", "red"
                    )
                    print_item(index, TOTAL, message)
        if verbose and not error:
            if isna(course_id):
                course_display = f"{long_name} ({canvas_course_id})"
            else:
                course_display = f"{course_id}"
            status_color = PRINT_COLOR_MAPS.get(tool_status, "")
            found_display = color(tool_status.upper(), status_color)
            message = f'"{tool_display}" {found_display} for {course_display}.'
            print_item(index, TOTAL, message)
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
                processed_errors_csv = processed_errors_csv[
                    processed_errors_csv["canvas user id"] != canvas_course_id
                ]
                processed_errors_csv.to_csv(PROCESSED_ERRORS_PATH, index=False)
            with open(PROCESSED_ERRORS_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id])

    if not use_id:
        tool = get_tool(tool)
    INSTANCE = "test" if test else "prod"
    report_path = get_report("courses", term, force_report, INSTANCE, verbose)
    year_display = f"{YEAR}_" if enable else ""
    tool_display = tool.replace(" ", "_") if use_id else tool
    test_display = "_test" if test else ""
    RESULT_PATH = COMMAND_PATH / f"{year_display}{tool_display}{test_display}.csv"
    start = get_start_index(force, RESULT_PATH)
    PROCESSED_COURSES = PROCESSED_ERRORS = None
    if enable:
        PROCESSED_STEM = (
            f"{tool_display}_tool_enable_processed_courses{test_display}.csv"
        )
        PROCESSED_PATH = PROCESSED / PROCESSED_STEM
        PROCESSED_ERRORS_STEM = (
            f"{tool_display}_tool_enable_processed_errors{test_display}.csv"
        )
        PROCESSED_ERRORS_PATH = PROCESSED / PROCESSED_ERRORS_STEM
        handle_clear_processed(
            clear_processed, [PROCESSED_PATH, PROCESSED_ERRORS_PATH], "courses"
        )
        PROCESSED_COURSES = get_processed(PROCESSED_PATH, "canvas course id")
        PROCESSED_ERRORS = get_processed(PROCESSED_ERRORS_PATH, "canvas course id")
    report, TOTAL = process_report(
        report_path, start, enable, PROCESSED_COURSES, PROCESSED_ERRORS, new, account_id
    )
    terms = report["term_id"].drop_duplicates().tolist()
    RESULTS = (
        create_directory(COMMAND_PATH / "Enabled")
        if enable
        else create_directory(COMMAND_PATH / "Reports")
    )
    if not force and not enable and not RESULT_PATH.exists():
        PREVIOUS_RESULTS = [result_file for result_file in Path(RESULTS).glob("*.csv")]
        PREVIOUS_RESULTS_FOR_TERM = dict()
        for term in terms:
            for result_file in PREVIOUS_RESULTS:
                if term in result_file.name:
                    PREVIOUS_RESULTS_FOR_TERM[term] = result_file
        TERMS_TO_RUN = list()
        for term in PREVIOUS_RESULTS_FOR_TERM:
            path_display = color(PREVIOUS_RESULTS_FOR_TERM[term], "green")
            color(
                f"REPORT FOR {tool.upper()} HAS ALREADY BEEN GENERATED FOR TERM"
                f" {term.upper()}: {path_display}",
                "yellow",
                True,
            )
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
            TOTAL = f"{len(report.index):,}"
            terms = report["term_id"].drop_duplicates().tolist()
            if not terms:
                echo("NO NEW TERMS TO PROCESS")
                color("FINISHED", "yellow", True)
                raise Exit()
    make_csv_paths(RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(start, "course")
    CANVAS = get_canvas(INSTANCE)
    tool_display = color(tool, "blue")
    STYLED_TERMS = color(f"{', '.join(terms)}", "yellow")
    if enable:
        if tool == "Course Materials @ Penn Libraries":
            separator = "\n\t"
            ACCOUNTS = color(
                f"{f'{separator}'.join(get_account_names(RESERVE_ACCOUNTS))}",
                "magenta",
            )
            echo(
                f') Enabling "{tool_display}" for {STYLED_TERMS} courses in:'
                f" \n\t{ACCOUNTS}"
            )
        else:
            echo(f') Enabling "{tool_display}" for {STYLED_TERMS} courses...')
    else:
        echo(f') Checking {STYLED_TERMS} courses for "{tool_display}"...')
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
    ) = process_result(terms, enable, RESULT_PATH, new)
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
        result_path,
    )
