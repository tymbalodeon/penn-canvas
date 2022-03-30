from datetime import datetime
from typing import Text, cast

from bs4 import BeautifulSoup, Tag
from canvasapi.course import Course
from canvasapi.tab import Tab
from flatten_json import flatten
from pandas import DataFrame, concat
from pytz import timezone
from requests import Session, get, request
from typer import echo

from .api import (
    Instance,
    get_account,
    get_course,
    request_external_url,
    validate_instance_name,
)
from .style import color


def get_blue_jeans_tabs(course: Course) -> list[Tab]:
    return [
        tab
        for tab in course.get_tabs()
        if tab.label in {"Virtual Meetings", "BlueJeans", "Blue Jeans"}
    ]


def get_tab_label_count(tabs: list[Tab], label: str) -> int:
    return len([tab for tab in tabs if tab.label == label])


def get_tab_type_counts(tabs: list[Tab]) -> tuple[int, int, int]:
    total_blue_jeans_tabs = get_tab_label_count(tabs, "Blue Jeans")
    total_bluejeans_tabs = get_tab_label_count(tabs, "BlueJeans")
    total_virtual_meetings_tabs = get_tab_label_count(tabs, "Virtual Meetings")
    return total_blue_jeans_tabs, total_bluejeans_tabs, total_virtual_meetings_tabs


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


def get_meetings(session: Session, url: str, meeting_status: str) -> list:
    meetings = session.get(url=url).json()["details"]
    for meeting in meetings:
        meeting["mtg_status"] = meeting_status
    return meetings


def get_meetings_data(
    lti_auth_token: str, lti_course_id: str, lti_user_id: str
) -> list[dict]:
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


def parse_meeting_ids(meeting: dict) -> dict:
    meeting["bj_meeting_id"] = (
        meeting["meetingLink"].split("/")[3] if "meetingLink" in meeting else "0"
    )
    meeting["bjc_conf_id"] = "0"
    meeting["bjc_rec_id"] = "0"
    meeting["bj_unknown_uuid"] = "0"
    if len(meeting["id"]) < 10:
        if "meetingLink" in meeting:
            meeting["bjc_conf_id"] = meeting["id"]
        else:
            meeting["bjc_rec_id"] = meeting["id"]
    else:
        meeting["bj_unknown_uuid"] = meeting["id"]
    return flatten(meeting)


def get_blue_jeans_report(
    course_id: int, instance_name: str | Instance = Instance.PRODUCTION
):
    instance = validate_instance_name(instance_name)
    course = get_course(course_id, instance=instance, verbose=True)
    term_name = (
        get_account(instance=instance)
        .get_enrollment_term(course.enrollment_term_id)
        .sis_term_id
    )
    echo(f"Getting Blue Jeans usage for course {color(course)}...")
    results = DataFrame()
    timestamp = datetime.now().astimezone(timezone("UTC"))
    course_data = {
        "canvas_acct_id": course.account_id,
        "canvas_course_id": course.id,
        "canvas_course_name": course.name,
        "term": term_name,
        "canvas_course_blueprint": course.blueprint,
        "canvas_course_status": course.workflow_state,
        "timestamp": timestamp,
    }
    meeting_name_data = {"mtg_name": "None"}
    blue_jeans_tabs = get_blue_jeans_tabs(course)
    for tab in blue_jeans_tabs:
        form = get_form_from_tab_url(tab.url, instance=instance)
        if not form:
            echo("Form not found for tab {tab.label}. Skipping...")
            continue
        try:
            lti_auth_token, lti_course_id, lti_user_id = get_lti_credentials(form)
        except Exception:
            echo("ERROR. Skipping...")
            continue
        meetings = get_meetings_data(lti_auth_token, lti_course_id, lti_user_id)
        meetings = [parse_meeting_ids(meeting) for meeting in meetings]
        tab_data = {
            "canvas_course_tab_id": tab.id,
            "canvas_course_tab_is_hidden": hasattr(tab, "hidden"),
            "canvas_course_tab_is_unused": hasattr(tab, "unused"),
            "canvas_course_tab_vis_group": tab.visibility,
        }
        course_with_tab_data = course_data | tab_data
        meetings = [meeting | course_with_tab_data for meeting in meetings]
        if meetings:
            meetings_data = DataFrame(meetings)
            meetings_data.rename(
                columns={
                    "listStartTime": "startTimeForList",
                    "title": "mtg_name",
                    "description": "mtg_desc",
                    "start": "mtg_start_time",
                    "end": "mtg_end_time",
                    "recordingTime": "mtg_recording_time",
                    "meetingLink": "mtg_join_link",
                    "recordingUrl": "mtg_play_link",
                },
                inplace=True,
            )
            results = concat([results, meetings_data], ignore_index=True, sort=True)
        else:
            meetings_data = DataFrame([course_with_tab_data | meeting_name_data])
            results = concat([results, meetings_data], ignore_index=True, sort=True)
    if not blue_jeans_tabs:
        course_data_frame = DataFrame([course_data | meeting_name_data])
        results = concat([results, course_data_frame], ignore_index=True, sort=True)
    blue_jeans_count, bluejeans_count, virtual_meetings_count = get_tab_type_counts(
        blue_jeans_tabs
    )
    echo(f'Number of "Blue Jeans" tabs: {blue_jeans_count}')
    echo(f'Number of "BlueJeans" tabs: {bluejeans_count}')
    echo(f'Number of "Virtual Meetings" tabs: {virtual_meetings_count}')
