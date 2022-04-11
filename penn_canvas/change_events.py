import pickle
from pathlib import Path

from tqdm import tqdm

from penn_canvas.api import (
    get_account,
    get_enrollment_term_id,
    request_canvas_api_endpoint,
)
from penn_canvas.helpers import format_timestamp, write_row
from penn_canvas.style import color, print_item


def is_relevant_event(event):
    return (
        "is_public" in event
        or "is_public_to_auth_users" in event
        or "public_syllabus" in event
        or "public_syllabus_to_auth" in event
    )


def request_url():
    term = get_enrollment_term_id("2022A")
    course_ids = [
        course.id for course in tqdm(get_account().get_courses(enrollment_term_id=term))
    ]
    total = len(course_ids)
    for index, course_id in enumerate(course_ids):
        endpoint = f"audit/course/courses/{course_id}"
        try:
            response = request_canvas_api_endpoint(endpoint)
            events = response.json()["events"]
            events = [
                event["event_data"]
                for event in events
                if event["event_type"] == "updated"
                and event["event_source"] == "manual"
            ]
            events = [event for event in events if is_relevant_event(event)]
            path = Path.home() / f"Desktop/{course_id}.pickle"
            if events:
                course = {course_id: events}
                with open(path, "wb") as pickle_file:
                    pickle.dump(course, pickle_file)
            message = (
                color(str(path), "green") if events else color("no events", "yellow")
            )
            print_item(index, total, f"{color(course_id)}: {message}")
        except Exception as error:
            print_item(index, total, color(f"ERROR: {course_id} ({error})", "red"))


def get_privatized(item):
    return item[1] is False


def read_data():
    path = Path.home() / "Desktop"
    courses = list(path.glob("*.pickle"))
    course_data = dict()
    for course in courses:
        with open(course, "rb") as pickle_file:
            data = pickle.load(pickle_file)
            for key, value in data.items():
                course_data[key] = value
    results = Path.home() / "Desktop/results.csv"
    write_row(
        results,
        [
            "canvas course id",
            "timestamp",
            "privatized",
            "privatized for auth",
            "privatized syllabus",
            "privatized syllabus for auth",
        ],
    )
    for key, value in course_data.items():
        for item in value:
            start_at = (
                public_change
            ) = public_to_auth_change = syllabus_change = syllabus_to_auth_change = None
            if "is_public" in item:
                public_change = get_privatized(item["is_public"])
            if "is_public_to_auth_users" in item:
                public_to_auth_change = get_privatized(item["is_public_to_auth_users"])
            if "public_syllabus" in item:
                syllabus_change = get_privatized(item["public_syllabus"])
            if "public_syllabus_to_auth" in item:
                syllabus_to_auth_change = get_privatized(
                    item["public_syllabus_to_auth"]
                )
            if "start_at" in item:
                start_at = next(iter(item["start_at"]), None)
                if start_at:
                    start_at = format_timestamp(start_at, localize=False)
            if not any(
                [
                    public_change,
                    public_to_auth_change,
                    syllabus_change,
                    syllabus_to_auth_change,
                ]
            ):
                continue
            row = [
                key,
                start_at,
                public_change,
                public_to_auth_change,
                syllabus_change,
                syllabus_to_auth_change,
            ]
            write_row(results, row, mode="a")
            print(
                key,
                start_at,
                public_change,
                public_to_auth_change,
                syllabus_change,
                syllabus_to_auth_change,
            )
    return course_data
