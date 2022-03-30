from datetime import datetime
from typing import Text, cast

from bs4 import BeautifulSoup, Tag
from canvasapi.course import Course
from canvasapi.requester import Requester
from canvasapi.tab import Tab
from flatten_json import flatten
from pandas import DataFrame, concat
from pytz import timezone
from requests import Session, get, request
from typer import echo

from penn_canvas.config import get_config_option

from .api import get_account, get_course
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


def get_form_from_tab_url(url: str) -> Tag:
    canvas_prod_url = get_config_option("canvas_urls", "canvas_prod_url")
    canvas_prod_key = get_config_option("canvas_keys", "canvas_prod_key")
    response = Requester(canvas_prod_url, canvas_prod_key).request("GET", _url=url)
    form_url = response.json().get("url")
    form_text = get(form_url).text
    beautiful_soup_form = BeautifulSoup(form_text, "html.parser")
    return cast(Tag, beautiful_soup_form.find("form"))


def get_lti_credentials(form: Tag) -> tuple[str, str, str]:
    input_fields = form.findAll("input")
    data = {field.get("name"): field.get("value") for field in input_fields}
    url = cast(Text, form.get("action"))
    response = request(method="post", url=url, data=data, allow_redirects=False)
    location = response.headers["Location"]
    auth_token = location.split("&")[0].split("=")[1]
    course_id = location.split("&")[2].split("=")[1]
    user_id = location.split("&")[3].split("=")[1]
    return auth_token, course_id, user_id


def get_meetings(session: Session, url: str, meeting_status: str) -> list:
    meetings = session.get(url=url).json().get("details")
    for meeting in meetings:
        meeting["mtg_status"] = meeting_status
    return meetings


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


def get_blue_jeans_report(course_id: int):
    data_frame = DataFrame()
    course = get_course(course_id, verbose=True)
    term_name = get_account().get_enrollment_term(course.enrollment_term_id).sis_term_id
    echo(f"Getting Blue Jeans usage for course {color(course)}...")
    timestamp_utc = datetime.now().astimezone(timezone("UTC"))
    blue_jeans_tabs = get_blue_jeans_tabs(course)
    blue_jeans_count, bluejeans_count, virtual_meetings_count = get_tab_type_counts(
        blue_jeans_tabs
    )
    for tab in blue_jeans_tabs:
        form = get_form_from_tab_url(tab.url)
        if not form:
            echo("Form not found for tab {tab.label}. Skipping...")
            continue
        try:
            lti_auth_token, lti_course_id, lti_user_id = get_lti_credentials(form)
        except Exception:
            echo("ERROR. Skipping...")
            continue
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
        meetings = upcoming_meetings + current_meetings + recorded_meetings
        meetings = [parse_meeting_ids(meeting) for meeting in meetings]
        if meetings:
            meetings_data_frame = DataFrame(meetings)
            meetings_data_frame["canvas_acct_id"] = course.account_id
            meetings_data_frame["canvas_course_blueprint"] = course.blueprint
            meetings_data_frame["canvas_course_id"] = course_id
            meetings_data_frame["canvas_course_name"] = course.name
            meetings_data_frame["canvas_course_status"] = course.workflow_state
            meetings_data_frame["canvas_course_tab_id"] = tab.id
            meetings_data_frame["canvas_course_tab_is_hidden"] = hasattr(tab, "hidden")
            meetings_data_frame["canvas_course_tab_is_unused"] = hasattr(tab, "unused")
            meetings_data_frame["canvas_course_tab_vis_group"] = tab.visibility
            meetings_data_frame["term"] = term_name
            meetings_data_frame["timestamp"] = timestamp_utc
            meetings_data_frame.rename(
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
            data_frame = concat(
                [data_frame, meetings_data_frame], ignore_index=True, sort=True
            )
        else:
            meetings_data_frame = DataFrame(
                [
                    {
                        "canvas_acct_id": course.account_id,
                        "canvas_course_id": course.id,
                        "canvas_course_name": course.name,
                        "mtg_name": "None",
                        "term": term_name,
                        "timestamp": timestamp_utc,
                        "canvas_course_blueprint": course.blueprint,
                        "canvas_course_status": course.workflow_state,
                        "canvas_course_tab_id": tab.id,
                        "canvas_course_tab_is_hidden": hasattr(tab, "hidden"),
                        "canvas_course_tab_is_unused": hasattr(tab, "unused"),
                        "canvas_course_tab_vis_group": tab.visibility,
                    }
                ]
            )
            data_frame = concat(
                [data_frame, meetings_data_frame], ignore_index=True, sort=True
            )
    if blue_jeans_tabs:
        course_data_frame = DataFrame(
            [
                {
                    "canvas_acct_id": course.account_id,
                    "canvas_course_id": course_id,
                    "canvas_course_name": course.name,
                    "canvas_course_blueprint": course.blueprint,
                    "canvas_course_status": course.workflow_state,
                    "mtg_name": "None",
                    "term": term_name,
                    "timestamp": timestamp_utc,
                }
            ]
        )
        data_frame = concat(
            [data_frame, course_data_frame], ignore_index=True, sort=True
        )
    echo(f"Number of Blue Jeans tabs: {blue_jeans_count}")
    echo(f"Number of BlueJeans tabs: {bluejeans_count}")
    echo(f"Number of Virtual Meetings tabs: {virtual_meetings_count}")
