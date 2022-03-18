from pathlib import Path

from loguru import logger
from pandas import isna, read_csv
from pandas.core.frame import DataFrame
from typer import echo, progressbar

from .api import Instance, get_course, validate_instance_name
from .helpers import (
    BASE_PATH,
    BOX_PATH,
    CURRENT_YEAR_AND_TERM,
    MONTH,
    TODAY_AS_Y_M_D,
    YEAR,
    color,
    create_directory,
    get_start_index,
    make_csv_paths,
    make_index_headers,
    print_skip_message,
    switch_logger_file,
)
from .notifier import send_email
from .report import get_report
from .style import print_item

COMMAND_PATH = create_directory(BASE_PATH / "Storage")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")
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


def process_report(report_path: Path, start: int) -> tuple[DataFrame, int]:
    report = read_csv(report_path)
    report = report.loc[:, HEADERS[:4]]
    report = report[report["storage used in MB"] > 0].copy()
    report = report.sort_values(by=["storage used in MB"])
    report = report.astype("string", errors="ignore")
    report = report[report["account id"].isin(SUB_ACCOUNTS)]
    report = report.reset_index(drop=True)
    total = len(report.index)
    report = report.loc[start:total, :]
    return report, total


def check_percent_storage(course: tuple, instance: Instance) -> tuple[str, bool, str]:
    canvas_id, sis_id, _, storage_used = course[1:]
    canvas_course = None
    needs_increase = False
    message = ""
    if isna(sis_id) or not sis_id:
        logger.warning(f'course "{canvas_id}" missing sis id')
        message = "missing sis id"
    else:
        try:
            canvas_course = get_course(canvas_id, instance=instance)
            percentage_used = float(storage_used) / canvas_course.storage_quota_mb
            if percentage_used >= 0.79:
                needs_increase = True
        except Exception as error_message:
            message = "course not found"
            logger_message = f"course {sis_id} ({canvas_id}) not found: {error_message}"
            logger.error(logger_message)
            send_email("Course Storage", logger_message)
    return canvas_course.name if canvas_course else "", needs_increase, message


def increase_quota(
    sis_id: str, increment_value: int, instance: Instance, sis_prefix="BAN_"
) -> tuple[int, str, int, int, str]:
    if CURRENT_YEAR_AND_TERM == "2022A":
        sis_prefix = "SRS_"
    if sis_id[:4] != sis_prefix:
        logger.warning(sis_id)
        middle = sis_id[:-5][-6:]
        sis_id = f"{sis_prefix}{sis_id[:11]}-{middle[:3]}-{middle[3:]} {sis_id[-5:]}"
    try:
        canvas_course = get_course(sis_id, use_sis_id=True, instance=instance)
        canvas_account_id = canvas_course.account_id
        status = ""
    except Exception as error_message:
        canvas_course = None
        canvas_account_id = "ERROR"
        status = "course not found"
        logger.error(f"course {sis_id} not found: {error_message}")
    if canvas_course:
        old_quota = canvas_course.storage_quota_mb
        new_quota = old_quota + increment_value
        try:
            canvas_course.update(course={"storage_quota_mb": new_quota})
        except Exception as error_message:
            new_quota = "ERROR"
            logger.error(
                f"course {sis_id} failed to update storage quota: {error_message}"
            )
    else:
        new_quota = old_quota = None
    return canvas_account_id, sis_id, old_quota, new_quota, status


def process_result(instance: Instance) -> tuple[int, int]:
    result = read_csv(RESULT_PATH, dtype=str)
    increased_count = len(result[result["error"] == ""].index)
    result = result.drop(result[result["error"] == "increase not required"].index)
    result = result.drop(result[result["error"] == "missing sis id"].index)
    error_count = len(result[result["error"] != ""].index)
    if error_count == 0:
        result.drop(columns=["error"], inplace=True)
    result = result.drop(columns=["index", "account id", "storage used in MB"])
    result = result.rename(columns={"id": "subaccount id", "sis id": "course code"})
    result.to_csv(RESULT_PATH, index=False)
    if instance == Instance.PRODUCTION and BOX_PATH.exists():
        current_month_directory = create_directory(
            BOX_PATH / f"Storage_Quota_Monitoring/{MONTH} {YEAR}"
        )
        result.to_csv(current_month_directory / RESULT_PATH.name, index=False)
    return increased_count, error_count


def print_messages(total: int, increased: int, errors: int):
    color("SUMMARY:", "yellow", True)
    echo(f"- Processed {color(total, 'magenta')} courses.")
    echo(f"- Increased storage quota for {color(increased, 'yellow')} courses.")
    if errors > 0:
        echo(f"- {color(f'Failed to find {str(errors)} courses.', 'red')}")
    color("FINISHED", "yellow", True)


def check_and_increase_storage(
    report: DataFrame,
    course: tuple,
    total: int,
    increment_value: int,
    instance: Instance,
    verbose: bool,
):
    index, canvas_id, sis_id = course[:3]
    course_name, needs_increase, message = check_percent_storage(course, instance)
    new_quota = old_quota = None
    status = ""
    if needs_increase:
        canvas_id, sis_id, old_quota, new_quota, status = increase_quota(
            message, increment_value, instance
        )
    elif not message:
        status = "increase not required"
    else:
        canvas_id = "ERROR"
        status = message
    row = [canvas_id, sis_id, old_quota, new_quota, status]
    columns = ["id", "sis id", "old quota", "new quota", "error"]
    report.loc[index, columns] = row
    report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)
    if verbose:
        increased = old_quota and new_quota
        increase_message = (
            f"increased {color(old_quota, 'yellow')} --> {color(new_quota, 'green')}"
            if increased
            else color(status, "yellow")
        )
        display_message = f"{color(course_name)}: {increase_message}"
        print_item(index, total, display_message)


def storage_main(
    increment_value: int,
    instance_name: str | Instance,
    force: bool,
    force_report: bool,
    verbose: bool,
):
    switch_logger_file(LOGS / "course_storage_{time}.log")
    instance = validate_instance_name(instance_name, verbose=True)
    report_path = get_report(
        "storage", CURRENT_YEAR_AND_TERM, force_report, instance, verbose
    )
    start = get_start_index(force, RESULT_PATH)
    report, total = process_report(report_path, start)
    make_csv_paths(RESULT_PATH, make_index_headers(HEADERS))
    print_skip_message(start, "course")
    echo(") Processing courses...")
    if verbose:
        for course in report.itertuples():
            check_and_increase_storage(
                report, course, total, increment_value, instance, verbose
            )
    else:
        with progressbar(report.itertuples(), length=total) as progress:
            for course in progress:
                check_and_increase_storage(
                    report, course, total, increment_value, instance, verbose
                )
    increased_count, error_count = process_result(instance)
    print_messages(total, increased_count, error_count)
