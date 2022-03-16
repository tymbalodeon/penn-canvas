from pathlib import Path

from pandas import isna, read_csv
from typer import echo

from penn_canvas.report import get_report

from .helpers import (
    BOX_PATH,
    CURRENT_YEAR_AND_TERM,
    MONTH,
    TODAY_AS_Y_M_D,
    YEAR,
    color,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    make_skip_message,
    toggle_progress_bar,
)
from .style import print_item

COMMAND_NAME = "Storage"
RESULTS = get_command_paths(COMMAND_NAME)["results"]
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_storage_result.csv"
HEADERS = [
    "id",
    "sis id",
    "account id",
    "storage used in MB",
    "old quota",
    "new quota",
    "error",
]
SUB_ACCOUNTS = [
    "132477",
    "99243",
    "99237",
    "132280",
    "107448",
    "132413",
    "128877",
    "99241",
    "99244",
    "99238",
    "99239",
    "131752",
    "131428",
    "99240",
    "132153",
    "82192",
]


def process_report(report_path, start):
    report = read_csv(report_path)
    report = report.loc[:, HEADERS[:4]]
    report = report[report["storage used in MB"] > 0].copy()
    report = report.sort_values(by=["storage used in MB"])
    report = report.astype("string", errors="ignore")
    report = report.reset_index(drop=True)
    total = len(report.index)
    report = report.loc[start:total, :]
    return report[report["account id"].isin(SUB_ACCOUNTS)], total


def check_percent_storage(course, canvas):
    canvas_id, sis_id = course[1:3]
    storage_used = course[-1]
    canvas_course = None
    needs_increase = False
    message = ""
    try:
        canvas_course = canvas.get_course(canvas_id)
        percentage_used = float(storage_used) / canvas_course.storage_quota_mb
        if percentage_used >= 0.79:
            is_na = isna(sis_id)
            needs_increase = False if is_na else True
            if is_na:
                message = "missing sis id"
    except Exception:
        message = "course not found"
    return canvas_course.name if canvas_course else "", needs_increase, message


def increase_quota(sis_id, canvas, increment_value, sis_prefix="SRS_"):
    if sis_id[:4] != sis_prefix:
        middle = sis_id[:-5][-6:]
        sis_id = f"{sis_prefix}{sis_id[:11]}-{middle[:3]}-{middle[3:]} {sis_id[-5:]}"
    try:
        canvas_course = canvas.get_course(sis_id, use_sis_id=True)
        canvas_account_id = canvas_course.account_id
        status = ""
    except Exception:
        canvas_course = None
        canvas_account_id = "ERROR"
        status = "course not found"
    if canvas_course:
        old_quota = canvas_course.storage_quota_mb
        new_quota = old_quota + increment_value
        try:
            canvas_course.update(course={"storage_quota_mb": new_quota})
        except Exception:
            new_quota = "ERROR"
    else:
        new_quota = old_quota = None
    return canvas_account_id, sis_id, old_quota, new_quota, status


def process_result():
    result = read_csv(RESULT_PATH, dtype=str)
    increased_count = len(result[result["error"] == ""].index)
    result.drop(result[result["error"] == "increase not required"].index, inplace=True)
    error_count = len(result[result["error"] != ""].index)
    if error_count == 0:
        result.drop(columns=["error"], inplace=True)
    result.drop(columns=["index", "account id", "storage used in MB"], inplace=True)
    result.rename(columns={"id": "subaccount id", "sis id": "course id"}, inplace=True)
    result.to_csv(RESULT_PATH, index=False)
    if BOX_PATH.exists():
        storage_shared_directory = BOX_PATH / "Storage_Quota_Monitoring"
        this_month_directory = next(
            (
                directory
                for directory in storage_shared_directory.iterdir()
                if YEAR in directory.name and MONTH in directory.name
            ),
            None,
        )
        try:
            if not this_month_directory:
                Path.mkdir(storage_shared_directory / f"{MONTH} {YEAR}")
                this_month_directory = next(
                    (
                        directory
                        for directory in storage_shared_directory.iterdir()
                        if YEAR in directory.name and MONTH in directory.name
                    ),
                    None,
                )
            box_result_path = (
                this_month_directory / RESULT_PATH.name
                if this_month_directory
                else None
            )
            if box_result_path:
                result.to_csv(box_result_path, index=False)
        except Exception as error:
            echo(f"- ERROR: {error}")
    return increased_count, error_count


def print_messages(total, increased, errors):
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total, 'magenta')} courses.")
    echo(f"- Increased storage quota for {color(increased, 'yellow')} courses.")
    if errors > 0:
        echo(f"- {color(f'Failed to find {str(errors)} courses.', 'red')}")
    color("FINISHED", "yellow", True)


def storage_main(test, verbose, force, increment_value=1000):
    def check_and_increase_storage(course, canvas, verbose, args):
        index, canvas_id, sis_id = course[:3]
        total, increase = args
        course_name, needs_increase, message = check_percent_storage(course, canvas)
        new_quota = old_quota = None
        status = ""
        if needs_increase:
            canvas_id, sis_id, old_quota, new_quota, status = increase_quota(
                message, canvas, increase
            )
        elif not message:
            status = "increase not required"
        else:
            canvas_id = "ERROR"
            status = message
        row = [canvas_id, sis_id, old_quota, new_quota, status]
        report.loc[
            index,
            [
                "id",
                "sis id",
                "old quota",
                "new quota",
                "error",
            ],
        ] = row
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)
        if verbose:
            increased = old_quota and new_quota
            increase_message = (
                f"increased {color(old_quota, 'yellow')} -->"
                f" {color(new_quota, 'green')}"
                if increased
                else status
            )
            display_message = f"{color(course_name)}: {increase_message}"
            print_item(index, total, display_message)

    report_path = get_report("storage", CURRENT_YEAR_AND_TERM)
    start = get_start_index(force, RESULT_PATH)
    report, total = process_report(report_path, start)
    make_csv_paths(RESULTS, RESULT_PATH, make_index_headers(HEADERS))
    make_skip_message(start, "course")
    instance = "test" if test else "prod"
    canvas = get_canvas(instance)
    echo(") Processing courses...")
    toggle_progress_bar(
        report,
        check_and_increase_storage,
        canvas,
        verbose,
        args=(total, increment_value),
    )
    increased_count, error_count = process_result()
    print_messages(total, increased_count, error_count)
