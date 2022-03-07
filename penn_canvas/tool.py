from csv import writer
from os import remove
from pathlib import Path

from pandas import DataFrame, concat, isna, read_csv
from typer import Exit, confirm, echo

from .helpers import (
    YEAR,
    add_headers_to_empty_files,
    color,
    drop_duplicate_errors,
    dynamic_to_csv,
    find_input,
    get_canvas,
    get_command_paths,
    get_processed,
    get_start_index,
    handle_clear_processed,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    process_input,
    toggle_progress_bar,
)

REPORTS, RESULTS, PROCESSED = get_command_paths("Tool", processed=True)
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


def get_account_names(accounts, canvas):
    return [
        account.name
        for account in [canvas.get_account(account) for account in accounts]
    ]


def check_tool(tool):
    if tool.lower() in {"reserve", "reserves"}:
        return "Course Materials @ Penn Libraries"
    elif tool.lower() == "panopto":
        return "Class Recordings"
    else:
        return tool


def cleanup_data(incoming_data, args):
    enable, processed_courses, processed_errors, new, account_id = args

    def cleanup_report(report, account_id=None):
        data = report[
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
        if account_id:
            data = data[data["canvas_account_id"] == account_id]
        if enable:
            data = data[~data["canvas_course_id"].isin(processed_courses)]
        return data

    if enable:
        data_frame = cleanup_report(incoming_data, account_id=account_id)
        data_frame.reset_index(drop=True, inplace=True)
        already_processed_count = len(processed_courses)
        if new:
            data_frame = data_frame[
                ~data_frame["canvas_course_id"].isin(processed_errors)
            ]
            already_processed_count = already_processed_count + len(processed_errors)
        if already_processed_count:
            message = color(
                f"SKIPPING {already_processed_count:,} PREVIOUSLY PROCESSED"
                f" {'COURSE' if already_processed_count == 1 else 'COURSES'}...",
                "yellow",
            )
            echo(f") {message}")
    else:
        data_frame = cleanup_report(incoming_data, account_id=account_id)
    return data_frame


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
        BASE = RESULTS / "Enabled" / YEAR
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
            drop_duplicate_errors([error_path])
        else:
            add_headers_to_empty_files(
                [enabled_path],
                ["canvas course id", "course id", "error"],
            )
    else:
        BASE = RESULTS / "Reports"
        if not BASE.exists():
            Path.mkdir(BASE)
        ENABLED_STEM = (
            f"{'_'.join(terms).replace('/', '')}_{result_path.stem}_REPORT_ENABLED.csv"
        )
        enabled_path = BASE / ENABLED_STEM
        enabled = enabled[["term id", "canvas course id", "course id"]]
        enabled = enabled.groupby(
            ["canvas course id", "term id"], group_keys=False
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
    tool, use_id, enable, test, verbose, new, force, clear_processed, account_id
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
                if tool == "turnitin":

                    def uses_turnitin(assignment):
                        if "url" in assignment.external_tool_tag_attributes:
                            return (
                                "turnitin"
                                in assignment.external_tool_tag_attributes["url"]
                            )
                        else:
                            return False

                    assignment = next(
                        assignment
                        for assignment in course.get_assignments()
                        if uses_turnitin(assignment)
                    )
                    tool_status = "enabled" if assignment else "disabled"
                else:
                    if use_id:
                        tool_tab = next((tab for tab in tabs if tab.id == tool), None)
                    else:
                        tool_tab = next(
                            (tab for tab in tabs if tab.label == tool), None
                        )
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
                    echo(f"- ({(index + 1):,}/{TOTAL}) {message}")
        if verbose and not error:
            if isna(course_id):
                course_display = f"{long_name} ({canvas_course_id})"
            else:
                course_display = f"{course_id}"
            status_color = PRINT_COLOR_MAPS.get(tool_status, "")
            found_display = color(tool_status.upper(), status_color)
            echo(
                f'- ({(index + 1):,}/{TOTAL}) "{tool_display}" {found_display} for'
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
                processed_errors_csv = processed_errors_csv[
                    processed_errors_csv["canvas user id"] != canvas_course_id
                ]
                processed_errors_csv.to_csv(PROCESSED_ERRORS_PATH, index=False)
            with open(PROCESSED_ERRORS_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id])

    tool = check_tool(tool)
    reports, missing_file_message = find_input(INPUT_FILE_NAME, REPORTS)
    RESULT_FILE_NAME = (
        f"{f'{YEAR}_' if enable else ''}{tool.replace(' ', '_')}"
        f"{'_test' if test else ''}.csv"
    )
    RESULT_PATH = RESULTS / RESULT_FILE_NAME
    START = get_start_index(force, RESULT_PATH)
    PROCESSED_COURSES = PROCESSED_ERRORS = None
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
    CLEANUP_HEADERS = [header.replace(" ", "_") for header in HEADERS[:7]]
    cleanup_data_args = (enable, PROCESSED_COURSES, PROCESSED_ERRORS, new, account_id)
    report, TOTAL = process_input(
        reports,
        INPUT_FILE_NAME,
        REPORTS,
        CLEANUP_HEADERS,
        cleanup_data,
        missing_file_message,
        cleanup_data_args,
        start=START,
    )
    if enable:
        report = report.loc[START:TOTAL, :]
    report["term_id"].fillna("N/A", inplace=True)
    terms = report["term_id"].drop_duplicates().tolist()
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
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    tool_display = color(tool, "blue")
    STYLED_TERMS = color(f"{', '.join(terms)}", "yellow")
    if enable:
        if tool == "Course Materials @ Penn Libraries":
            separator = "\n\t"
            ACCOUNTS = color(
                f"{f'{separator}'.join(get_account_names(RESERVE_ACCOUNTS, CANVAS))}",
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
