from csv import writer
from datetime import datetime
from os import remove
from pathlib import Path

from pandas import DataFrame, concat, isna, read_csv
from typer import Exit, confirm, echo

from .helpers import (
    colorize,
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
    if tool.lower() in ["reserve", "reserves"]:
        return "Course Materials @ Penn Libraries"
    else:
        return tool


def find_course_report():
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
        TODAYS_REPORTS = list(filter(lambda report: TODAY in report.name, CSV_FILES))

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

            echo(f"- Found {total} {report_display}:")

            FOUND_PATHS = list()

            for path in TODAYS_REPORTS:
                FOUND_PATHS.append(colorize(path.stem, "green"))

            for path in FOUND_PATHS:
                echo(f"- {path}")

            return TODAYS_REPORTS, report_display


def cleanup_report(reports, report_display, start=0):
    echo(f") Preparing {report_display}...")

    data_frames = list()

    for report in reports:
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
        data = data.astype("string", copy=False, errors="ignore")
        data_frames.append(data)

    data_frame = concat(data_frames, ignore_index=True)
    total = len(data_frame.index)
    data_frame = data_frame.loc[start:total, :]
    data_frame["term_id"].fillna("N/A", inplace=True)
    terms = data_frame["term_id"].drop_duplicates().tolist()

    return data_frame, str(total), terms


def get_processed_courses(processed_path):
    if processed_path.is_file():
        result = read_csv(processed_path)
        result = result.astype("string", copy=False, errors="ignore")
        return result["canvas_course_id"].tolist()
    else:
        make_csv_paths(PROCESSED, processed_path, ["canvas_course_id"])
        return list()


def process_result(tool, terms, enable, result_path):
    result = read_csv(result_path)
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
        DataFrame.sort_values, "course_id"
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
        final_path = (
            RESULTS / f"{'_'.join(terms).replace('/', '')}_{result_path.stem}.csv"
        )
        result_path = result_path.rename(final_path)

    return (
        str(ENABLED_COUNT),
        str(ALREADY_ENABLED_COUNT),
        DISABLED_COUNT,
        NOT_FOUND_COUNT,
        NOT_PARTICIPATING_COUNT,
        str(ERROR_COUNT),
        result_path,
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
    tool = colorize(tool, "cyan")
    colorize("SUMMARY:", "yellow", True)
    echo(f"- Processed {colorize(total, 'magenta')} courses.")
    total_enabled = colorize(enabled, "green")
    total_already_enabled = colorize(already_enabled, "green")

    if enable:
        echo(f'- Enabled "{tool}" for {total_enabled} courses.')
        if int(total_already_enabled):
            echo(
                f'- Found {total_already_enabled} courses with "{tool}" already'
                " enabled."
            )
    else:
        echo(f'- Found {total_already_enabled} courses with "{tool}" enabled.')
        echo(
            f'- Found {colorize(disabled, "magenta")} courses with disabled "{tool}"'
            " tab."
        )

    if int(not_found):
        message = colorize(not_found, "yellow")
        echo(f'- Found {message} courses with no "{tool}" tab.')

    if int(not_participating):
        message = colorize(not_participating, "yellow")
        echo(
            f"- Found {message} courses in schools not participating in automatic"
            f' enabling of "{tool}".'
        )

    if int(error):
        message = colorize(f"Encountered errors for {error} courses.", "red")
        echo(f"- {message}")
        result_path_display = colorize(result_path, "green")
        echo(f"- Details recorded to result file: {result_path_display}")

    colorize("FINISHED", "yellow", True)


def tool_main(tool, use_id, enable, test, verbose, force, clear_processed):
    def check_tool_usage(course, canvas, verbose, args):
        if len(args) == 4:
            tool, use_id, enable, PROCESSED_COURSES = args
        else:
            tool, use_id, enable = args

        tool_display = colorize(tool, "cyan")
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
        found = tool_status.upper()
        color = "red"
        error = False

        if enable and canvas_course_id in PROCESSED_COURSES:
            tool_status = "already processed"
            found = tool_status.upper()
            color = "yellow"
        elif (
            enable
            and tool == "Course Materials @ Penn Libraries"
            and canvas_account_id not in RESERVE_ACCOUNTS
        ):
            tool_status = "school not participating"
            found = f"NOT ENABLED ({tool_status.upper()})"
            color = "yellow"
        elif not enable and status != "active" and verbose:
            found = tool_status.upper()
            color = "yellow"
        else:
            try:
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()

                if use_id:
                    tool_tab = next(filter(lambda tab: tab.id == tool, tabs), None)
                else:
                    tool_tab = next(filter(lambda tab: tab.label == tool, tabs), None)

                if not tool_tab:
                    found = tool_status.upper()
                    color = "yellow"
                elif tool_tab.visibility == "public":
                    tool_status = "already enabled"

                    if verbose:
                        if enable:
                            found = tool_status.upper()
                            color = "yellow"
                        else:
                            found = "ENABLED"
                            color = "green"
                elif enable:
                    tool_tab.update(hidden=False, position=3)
                    tool_status = "enabled"

                    if verbose:
                        found = tool_status.upper()
                        color = "green"
                else:
                    tool_status = "disabled"

                    if verbose:
                        found = tool_status.upper()
                        color = "yellow"
            except Exception as error_message:
                tool_status = f"{str(error_message)}"
                error = True

                if verbose:
                    message = colorize(
                        f"ERROR: Failed to process {course_id} ({error_message})", "red"
                    )
                    echo(f"- ({index + 1}/{total}) {message}")

        if verbose and not error:
            if isna(course_id):
                course_display = f"{long_name} ({canvas_course_id})"
            else:
                course_display = f"{course_id}"

            found_display = colorize(found, color)
            echo(
                f'- ({index + 1}/{total}) "{tool_display}" {found_display} for'
                f" {course_display}."
            )

        if isna(course_id):
            report.at[index, "course_id"] = f"{short_name} ({canvas_account_id})"

        report.at[index, "tool status"] = tool_status
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

        if enable and tool_status != "already processed":
            with open(PROCESSED_PATH, "a+", newline="") as processed_file:
                writer(processed_file).writerow([canvas_course_id])

    tool = check_tool(tool)
    REPORTS, report_display = find_course_report()
    RESULT_FILE_NAME = (
        f"{tool.replace(' ', '_')}_tool_{'enable' if enable else 'report'}"
        f"_{TODAY_AS_Y_M_D}.csv"
    )
    RESULT_PATH = RESULTS / RESULT_FILE_NAME
    START = get_start_index(force, RESULT_PATH)
    report, total, terms = cleanup_report(REPORTS, report_display, START)

    if not enable and not force:
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
            total = str(len(report.index))
            terms = report["term_id"].drop_duplicates().tolist()

            if not terms:
                echo("NO NEW TERMS TO PROCESS")
                colorize("FINISHED", "yellow", True)

                raise Exit()

    if enable:
        PROCESSED_PATH = (
            PROCESSED / f"{tool.replace(' ', '_')}_tool_enable_processed_courses.csv"
        )

        if clear_processed:
            proceed = confirm(
                "You have asked to clear the list of courses already processed."
                " This list makes subsequent runs of the command faster. Are you sure"
                " you want to do this?"
            )
        else:
            proceed = False

        if proceed:
            echo(") Clearing list of courses already processed...")

            if PROCESSED_PATH.exists():
                remove(PROCESSED_PATH)
        else:
            echo(") Finding courses already processed...")

        PROCESSED_COURSES = get_processed_courses(PROCESSED_PATH)

    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    tool_display = colorize(tool, "cyan")
    TERMS_DISPLAY = map(
        lambda term: colorize(term, "blue"),
        terms,
    )
    STYLED_TERMS = f"{', '.join(TERMS_DISPLAY)}"

    if enable:
        if tool == "Course Materials @ Penn Libraries":
            ACCOUNTS_DISPLAY = map(
                lambda account: colorize(account, "magenta"),
                RESERVE_ACCOUNTS,
            )
            ACCOUNTS = f"{', '.join(ACCOUNTS_DISPLAY)}"
            echo(
                f') Enabling "{tool_display}" for {STYLED_TERMS} courses in'
                f" {ACCOUNTS}..."
            )
        else:
            echo(f') Enabling "{tool_display}" for {STYLED_TERMS} courses...')
    else:
        echo(f') Checking {STYLED_TERMS} courses for "{tool_display}"...')

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
