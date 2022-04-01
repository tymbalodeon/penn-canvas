from pathlib import Path
from typing import Optional, Text, cast

from bs4 import BeautifulSoup, Tag
from canvasapi.course import Course
from canvasapi.tab import Tab
from loguru import logger
from pandas import DataFrame, isna, read_csv
from requests import Session, get, request
from typer import echo

from penn_canvas.helpers import (
    BASE_PATH,
    create_directory,
    get_start_index,
    switch_logger_file,
)
from penn_canvas.report import Report, ReportType, create_reports

from .api import (
    Instance,
    get_course,
    get_sub_account_ids,
    request_external_url,
    validate_instance_name,
)
from .style import color, print_item

COMMAND_PATH = create_directory(BASE_PATH / "Blue Jeans")
LOGS = create_directory(COMMAND_PATH / "Logs")
BLUE_JEANS_LABELS = {"Virtual Meetings", "BlueJeans", "Blue Jeans"}


def is_active_blue_jeans_tab(tab: Tab) -> bool:
    return tab.label in BLUE_JEANS_LABELS and tab.visibility == "public"


def get_blue_jeans_tab(course: Course) -> Optional[Tab]:
    tabs = course.get_tabs()
    blue_jeans_tabs = (tab for tab in tabs if is_active_blue_jeans_tab(tab))
    return next(blue_jeans_tabs, None)


def get_form_from_tab_url(url: str, instance: Instance) -> Tag:
    response = request_external_url(url, instance=instance)
    form_url = response.json()["url"]
    form_text = get(form_url).text
    beautiful_soup_form = BeautifulSoup(form_text, "html.parser")
    return cast(Tag, beautiful_soup_form.find("form"))


def get_lti_credentials(form: Tag) -> tuple[str, str, str]:
    input_fields = form.findAll("input")
    data = {field["name"]: field["value"] for field in input_fields}
    url = cast(Text, form["action"])
    response = request(method="post", url=url, data=data, allow_redirects=False)
    location = response.headers["Location"]
    auth_token = location.split("&")[0].split("=")[1]
    course_id = location.split("&")[2].split("=")[1]
    user_id = location.split("&")[3].split("=")[1]
    return auth_token, course_id, user_id


def get_meeting_object(meeting, status):
    return meeting["recordingTime"], status


def get_meetings(session: Session, url: str, meeting_status: str) -> list[tuple]:
    meetings = session.get(url=url).json()["details"]
    meetings = [get_meeting_object(meeting, meeting_status) for meeting in meetings]
    return meetings


def get_meetings_data(
    lti_auth_token: str, lti_course_id: str, lti_user_id: str
) -> list[tuple]:
    session = Session()
    session.headers.update({"Authorization": f"Bearer {lti_auth_token}"})
    base_url = "https://canvaslms.bluejeansint.com/api/canvas/course/"
    user_url = f"{base_url}{lti_course_id}/user/{lti_user_id}/"
    upcoming_url = f"{user_url}conferences?limit=100"
    upcoming_meetings = get_meetings(session, upcoming_url, "upcoming")
    current_url = f"{user_url}conferences?limit=100&current=true"
    current_meetings = get_meetings(session, current_url, "current")
    recorded_url = f"{user_url}recordings?limit=100"
    recorded_meetings = get_meetings(session, recorded_url, "recorded")
    return upcoming_meetings + current_meetings + recorded_meetings


def get_meetings_from_tab(tab: Tab, instance: Instance):
    form = get_form_from_tab_url(tab.url, instance=instance)
    if not form:
        echo(color("ERROR getting Blue Jeans form", "yellow"))
    try:
        lti_auth_token, lti_course_id, lti_user_id = get_lti_credentials(form)
    except Exception:
        echo(color("ERROR getting LTI credentials", "yellow"))
        return list()
    return get_meetings_data(lti_auth_token, lti_course_id, lti_user_id)


def get_blue_jeans_data(
    report: DataFrame,
    total: int,
    course: tuple,
    result_path: Path,
    instance: Instance,
    verbose: bool,
):
    (
        index,
        canvas_course_id,
        course_id,
        short_name,
        canvas_account_id,
    ) = course[:5]
    try:
        canvas_course = get_course(canvas_course_id, instance=instance)
        blue_jeans_tab = get_blue_jeans_tab(canvas_course)
    except Exception as error:
        logger.error(error)
        blue_jeans_tab = None
        canvas_course = "Not Found"
    enabled = bool(blue_jeans_tab)
    meetings = list()
    if blue_jeans_tab:
        meetings = get_meetings_from_tab(blue_jeans_tab, instance=instance)
    if isna(course_id):
        report.at[index, "course_id"] = f"{short_name} ({canvas_account_id})"
    report.at[index, "tool status"] = enabled
    meetings_count = len(meetings)
    report.at[index, "meetings count"] = meetings_count
    report.loc[index].to_frame().T.to_csv(result_path, mode="a", header=False)
    if verbose:
        status_display = (
            color("FOUND", "green") if enabled else color("NOT ENABLED", "yellow")
        )
        message = f"{color(canvas_course)}: {status_display}"
        print_item(index, total, message)


def process_report(
    report_path: Path, start: int, account_id: int
) -> tuple[DataFrame, int]:
    report = read_csv(report_path)
    report = report[
        [
            "canvas_course_id",
            "course_id",
            "short_name",
            "canvas_account_id",
            "term_id",
            "status",
        ]
    ]
    report.drop_duplicates(inplace=True)
    report.sort_values("course_id", inplace=True, ignore_index=True)
    report = report.astype("string", copy=False, errors="ignore")
    if account_id:
        sub_accounts = get_sub_account_ids(account_id)
        report = report[report["canvas_account_id"].isin(sub_accounts)]
    total = len(report.index)
    report["term_id"].fillna("N/A", inplace=True)
    report = report.loc[start:total, :]
    return report, total


def blue_jeans_main(
    terms: str | list[str],
    instance_name: str | Instance,
    account_id: int,
    verbose: bool,
    force: bool,
    force_report: bool,
):
    instance = validate_instance_name(instance_name, verbose=not verbose)
    switch_logger_file(LOGS, "blue_jeans", instance.name)
    report_objects = [
        Report(ReportType.COURSES, instance=instance, term=term, force=force_report)
        for term in terms
    ]
    report_paths = create_reports(report_objects, verbose=verbose)
    for path in report_paths:
        result_path = COMMAND_PATH / f"Blue_Jeans{path.stem}.csv"
        start = get_start_index(force, result_path)
        report, total = process_report(path, start, account_id)
        for course in report.itertuples():
            get_blue_jeans_data(report, total, course, result_path, instance, verbose)
