from csv import writer
from pathlib import Path
from typing import Optional

from canvasapi.user import User
from loguru import logger
from pandas import DataFrame
from pandas.io.parsers.readers import read_csv
from tqdm import tqdm
from typer import Exit, echo, progressbar
from ua_parser import user_agent_parser

from penn_canvas.helpers import (
    BASE_PATH,
    create_directory,
    get_course_ids_from_input,
    make_list_from_optional_iterable,
    switch_logger_file,
)

from .api import (
    Instance,
    collect,
    format_instance_name,
    get_course,
    print_instance,
    validate_instance_name,
)
from .style import color, print_item

COMMAND_PATH = create_directory(BASE_PATH / "Browser")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")


def get_user_account_data(user: User) -> list:
    try:
        email = user.email
    except Exception as error:
        logger.error(error)
        email = ""
    return [user.id, user.name, email]


def parse_user_agent_string(
    user_agent_string: str, verbose: bool, index: int, total: int
) -> str:
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
    user_agent_string = " / ".join([browser_name, os_name, device_name])
    if verbose:
        print_item(index, total, color(user_agent_string, "cyan"), prefix="\t-")
    return user_agent_string


def get_user_agents(
    user: User, result_path: Path, index: int, total: int, verbose: bool
):
    if verbose:
        print_item(index, total, f"Fetching user agents for {color(user)}...")
    user_agents = {
        page_view.user_agent
        for page_view in tqdm(user.get_page_views())
        if page_view.user_agent
    }
    if verbose:
        echo(f"\t* Parsing user agents for {color(user)}...")
    user_agents = {
        parse_user_agent_string(user_agent, verbose, index, len(user_agents))
        for index, user_agent in enumerate(user_agents)
    }
    if verbose:
        user_agents_display = color(len(user_agents), "yellow")
        echo(f"\tFOUND {user_agents_display} unique agents.")
    user_data = get_user_account_data(user)
    row = user_data + make_list_from_optional_iterable(user_agents)
    with open(result_path, "a") as result_file:
        writer(result_file).writerow(row)
    return len(row)


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
    result_path = RESULTS / f"{course}_browser_data{format_instance_name(instance)}.csv"
    users = collect(course.get_users(enrollment_type=["student"]))[:2]
    max_row_length = 0
    for index, user in enumerate(users):
        length_of_row = get_user_agents(user, result_path, index, len(users), verbose)
        if length_of_row > max_row_length:
            max_row_length = length_of_row
    columns = ["Canvas User ID", "Name", "Email"]
    number_of_user_agent_columns = max_row_length - len(columns)
    user_agent_columns = list()
    for index in range(1, number_of_user_agent_columns + 1):
        user_agent_columns.append(f"User Agent {index}")
    columns = columns + user_agent_columns
    results = read_csv(result_path, names=columns, header=None)
    data_frame = DataFrame(results, columns=columns)
    data_frame.to_csv(result_path, index=False)


def browser_main(
    course_ids: Optional[int | list[int]], instance_name: str, verbose: bool
):
    instance = validate_instance_name(instance_name)
    switch_logger_file(LOGS, "browser", instance.name)
    if not course_ids:
        echo("NO COURSE(S) PROVIDED")
        raise Exit()
    else:
        print_instance(instance)
        courses = get_course_ids_from_input(course_ids)
    total_courses = len(courses)
    if verbose:
        for index, course in enumerate(courses):
            get_course_browser_data(course, instance, verbose, index, total_courses)
    else:
        with progressbar(courses, length=total_courses) as progress:
            for course in progress:
                get_course_browser_data(course, instance, verbose)
