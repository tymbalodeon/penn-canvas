from csv import writer
from os import remove
from pathlib import Path

from pandas import DataFrame, concat, isna, read_csv
from typer import Exit, confirm, echo, progressbar

from penn_canvas.report import get_report
from penn_canvas.style import print_item

from .api import (
    Instance,
    format_instance_name,
    get_account,
    get_course,
    validate_instance_name,
)
from .helpers import (
    BASE_PATH,
    YEAR,
    add_headers_to_empty_files,
    color,
    create_directory,
    drop_duplicate_errors,
    dynamic_to_csv,
    get_processed,
    get_start_index,
    handle_clear_processed,
    make_csv_paths,
    make_index_headers,
    print_skip_message,
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

PRINT_COLOR_MAPS = {
    "not found": "red",
    "already processed": "yellow",
    "unsupported": "yellow",
    "already enabled": "cyan",
    "enabled": "green",
    "disabled": "yellow",
}


def get_account_names(accounts: list[str]) -> list[str]:
    return [get_account(int(account)).name for account in accounts]


def get_tool(tool: str) -> str:
    tool = tool.lower()
    if tool in {"reserve", "reserves"}:
        return "Course Materials @ Penn Libraries"
    elif tool == "panopto":
        return "Class Recordings"
    else:
        return tool


def process_report(
    report_path: Path,
    start: int,
    enable: int,
    processed_courses: list[str],
    processed_errors: list[str],
    new: bool,
    account_id: str,
) -> tuple[DataFrame, int]:
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
            print_skip_message(already_processed_count, "course", current_report=True)
        total = len(report.index)
        report = report.loc[start:total, :]
    else:
        total = len(report.index)
    report["term_id"].fillna("N/A", inplace=True)
    return report, total


def process_result(
    terms: list[str], enable: bool, result_path: Path, new: int
) -> tuple[int, int, int, int, int, int, Path]:
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
    tool: str,
    enable: bool,
    enabled: int,
    already_enabled: int,
    disabled: int,
    not_found: int,
    not_supported: int,
    error: int,
    total: int,
    result_path: Path,
):
    tool_display = color(tool, "blue")
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total, 'magenta')} courses.")
    total_enabled = color(enabled, "green" if enabled else "yellow")
    total_already_enabled = color(already_enabled, "cyan")
    if enable:
        echo(f'- Enabled "{tool_display}" for {total_enabled} courses.')
        if already_enabled:
            echo(
                f'- Found {total_already_enabled} courses with "{tool_display}" already'
                " enabled."
            )
    else:
        echo(f'- Found {total_enabled} courses with "{tool_display}" enabled.')
        echo(
            f'- Found {color(disabled, "yellow")} courses with disabled'
            f' "{tool_display}" tab.'
        )
    if not_found:
        message = color(not_found, "yellow")
        echo(f'- Found {message} courses with no "{tool_display}" tab.')
    if not_supported:
        message = color(not_supported, "yellow")
        echo(
            f"- Found {message} courses in schools not participating in automatic"
            f' enabling of "{tool_display}".'
        )
    if error:
        message = color(f"Encountered errors for {error:,} courses.", "red")
        echo(f"- {message}")
        result_path_display = color(result_path, "green")
        echo(f"- Details recorded to result file: {result_path_display}")
    color("FINISHED", "yellow", True)


def check_tool_usage(
    report: DataFrame,
    total: int,
    course: tuple,
    tool: str,
    use_id: bool,
    enable: bool,
    result_path: Path,
    processed_path: Path,
    processed_errors: list[str],
    processed_errors_path: Path,
    instance: Instance,
    verbose: bool,
):
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
            canvas_course = get_course(canvas_course_id, instance=instance)
            tabs = canvas_course.get_tabs()
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
                print_item(index, total, message)
    if verbose and not error:
        if isna(course_id):
            course_display = f"{long_name} ({canvas_course_id})"
        else:
            course_display = f"{course_id}"
        status_color = PRINT_COLOR_MAPS.get(tool_status, "")
        found_display = color(tool_status.upper(), status_color)
        message = f'"{tool_display}" {found_display} for {course_display}.'
        print_item(index, total, message)
    if isna(course_id):
        report.at[index, "course_id"] = f"{short_name} ({canvas_account_id})"
    report.at[index, "tool status"] = tool_status
    report.loc[index].to_frame().T.to_csv(result_path, mode="a", header=False)
    if enable and tool_status in {"already enabled", "enabled", "unsupported"}:
        with open(processed_path, "a+", newline="") as processed_file:
            writer(processed_file).writerow([canvas_course_id])
    elif enable and canvas_course_id not in processed_errors:
        if canvas_course_id in processed_errors:
            processed_errors_csv = read_csv(processed_errors_path)
            processed_errors_csv = processed_errors_csv[
                processed_errors_csv["canvas user id"] != canvas_course_id
            ]
            processed_errors_csv.to_csv(processed_errors_path, index=False)
        with open(processed_errors_path, "a+", newline="") as processed_file:
            writer(processed_file).writerow([canvas_course_id])


def tool_main(
    tool: str,
    term: str,
    use_id: bool,
    enable: bool,
    instance_name: str | Instance,
    verbose: bool,
    new: bool,
    force: bool,
    force_report: bool,
    clear_processed: bool,
    account_id: str,
):

    instance = validate_instance_name(instance_name, verbose=True)
    if not use_id:
        tool = get_tool(tool)
    report_path = get_report("courses", term, force_report, instance, verbose)
    year_display = f"{YEAR}_" if enable else ""
    tool_display = tool.replace(" ", "_") if use_id else tool
    instance_display = format_instance_name(instance)
    result_path = COMMAND_PATH / f"{year_display}{tool_display}{instance_display}.csv"
    start = get_start_index(force, result_path)
    processed_stem = (
        f"{tool_display}_tool_enable_processed_courses{instance_display}.csv"
    )
    processed_path = PROCESSED / processed_stem
    processed_errors_stem = (
        f"{tool_display}_tool_enable_processed_errors{instance_display}.csv"
    )
    processed_errors_path = PROCESSED / processed_errors_stem
    handle_clear_processed(
        clear_processed, [processed_path, processed_errors_path], "courses"
    )
    processed_courses = get_processed(processed_path, "canvas course id")
    processed_errors = get_processed(processed_errors_path, "canvas course id")
    report, total = process_report(
        report_path, start, enable, processed_courses, processed_errors, new, account_id
    )
    terms = report["term_id"].drop_duplicates().tolist()
    RESULTS = (
        create_directory(COMMAND_PATH / "Enabled")
        if enable
        else create_directory(COMMAND_PATH / "Reports")
    )
    if not force and not enable and not result_path.exists():
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
            terms = report["term_id"].drop_duplicates().tolist()
            if not terms:
                echo("NO NEW TERMS TO PROCESS")
                color("FINISHED", "yellow", True)
                raise Exit()
    make_csv_paths(result_path, make_index_headers(HEADERS))
    print_skip_message(start, "course")
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
    if verbose:
        for course in report.itertuples():
            check_tool_usage(
                report,
                total,
                course,
                tool,
                use_id,
                enable,
                result_path,
                processed_path,
                processed_errors,
                processed_errors_path,
                instance,
                verbose,
            )
    else:
        with progressbar(report.itertuples(), length=total) as progress:
            for course in progress:
                check_tool_usage(
                    report,
                    total,
                    course,
                    tool,
                    use_id,
                    enable,
                    result_path,
                    processed_path,
                    processed_errors,
                    processed_errors_path,
                    instance,
                    verbose,
                )
    (
        enabled,
        already_enabled,
        disabled,
        not_found,
        not_participating,
        error,
        result_path,
    ) = process_result(terms, enable, result_path, new)
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
