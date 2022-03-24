from typing import Optional

from canvasapi.user import User
from pandas import DataFrame
from tqdm import tqdm
from typer import echo, progressbar
from ua_parser import user_agent_parser

from penn_canvas.helpers import (
    BASE_PATH,
    create_directory,
    make_list,
    switch_logger_file,
)
from penn_canvas.report import get_course_ids_from_reports

from .api import Instance, collect, get_course, print_instance, validate_instance_name
from .style import color, print_item

COMMAND_PATH = create_directory(BASE_PATH / "Archive")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")


def get_user_account_data(user: User) -> list:
    return [user.id, user.name, user.email]


def parse_user_agent_string(user_agent_string: str) -> str:
    browser = user_agent_parser.ParseUserAgent(user_agent_string)
    user_os = user_agent_parser.ParseOS(user_agent_string)
    browser_family = browser["family"]
    browser_major = f" {browser['major']}" if browser["major"] else ""
    browser_minor = f".{browser['minor']}" if browser["minor"] else ""
    browser_patch = f".{browser['patch']}" if browser["patch"] else ""
    os_family = user_os["family"]
    os_major = f" {user_os['major']}" if user_os["major"] else ""
    os_minor = f".{user_os['minor']}" if user_os["minor"] else ""
    os_patch = f".{user_os['patch']}" if user_os["patch"] else ""
    browser_name = f"{browser_family}{browser_major}{browser_minor}{browser_patch}"
    os_name = f"{os_family}{os_major}{os_minor}{os_patch}"
    device_name = user_agent_parser.ParseDevice(user_agent_string)["family"]
    return " / ".join([browser_name, os_name, device_name])


def get_user_agents(user: User, index: int, total: int, verbose: bool) -> list:
    if verbose:
        echo(f") Fetching user agents for {color(user)}...")
    user_agents = {
        parse_user_agent_string(page_view.user_agent)
        for page_view in tqdm(user.get_page_views())
        if page_view.user_agent
    }
    user_display = color(user.name)
    user_agents_display = color(len(user_agents), "yellow")
    message = f"{user_display} used {user_agents_display} different agents."
    if verbose:
        print_item(index, total, message)
    return make_list(user_agents)


def fill_empty_columns(data_list: list, total_columns: int) -> list:
    if len(data_list) < total_columns:
        return data_list + ([None] * (total_columns - len(data_list)))
    else:
        return data_list


def get_course_browser_data(
    course_id: int, instance: Instance, verbose: bool, index=0, total=0
):
    course = get_course(course_id, instance=instance)
    if verbose:
        echo(f"==== COURSE {index + 1:,} of {total:,} ====")
        echo(f") Fetching users for {color(course, 'blue')}...")
    users = collect(course.get_users(enrollment_type=["student"]))
    users = [
        get_user_account_data(user) + get_user_agents(user, index, len(users), verbose)
        for index, user in enumerate(users)
    ]
    columns = ["Canvas User ID", "Name", "Email"]
    number_of_user_agent_columns = max({len(user) for user in users}) - len(columns)
    columns = columns + ["User Agent"] * number_of_user_agent_columns
    users = [fill_empty_columns(user, len(columns)) for user in users]
    data_frame = DataFrame(users, columns=columns)
    data_frame.to_csv(RESULTS / "results.csv", index=False)


def browser_main(
    course_ids: Optional[int | list[int]],
    terms: str | list[str],
    instance_name: str,
    force_report: bool,
    verbose: bool,
):
    instance = validate_instance_name(instance_name)
    switch_logger_file(LOGS, "browser", instance.name)
    if not course_ids:
        courses = get_course_ids_from_reports(terms, instance, force_report, verbose)
    else:
        print_instance(instance)
        courses = make_list(course_ids)
    total_courses = len(courses)
    if verbose:
        for index, course in enumerate(courses):
            get_course_browser_data(course, instance, verbose, index, total_courses)
    else:
        with progressbar(courses, length=total_courses) as progress:
            for course in progress:
                get_course_browser_data(course, instance, verbose)
