from csv import reader, writer
from pathlib import Path
from typing import Optional

from canvasapi.user import User
from loguru import logger
from pandas import read_csv
from tqdm import tqdm
from typer import Exit, echo, progressbar
from ua_parser import user_agent_parser

from penn_canvas.helpers import (
    BASE_PATH,
    create_directory,
    get_course_ids_from_input,
    make_list_from_optional_iterable,
    print_task_complete_message,
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
    if result_path.is_file():
        results = read_csv(result_path, usecols=[0], header=None)[0].tolist()
        if user.id in results:
            print_item(
                index, total, f"User agents already processed for {color(user)}..."
            )
            return
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


def fill_empty_columns(data_list: list, total_columns: int) -> list:
    if len(data_list) < total_columns:
        return data_list + ([None] * (total_columns - len(data_list)))
    else:
        return data_list


def get_course_browser_data(
    course_id: int, instance: Instance, verbose: bool, index=0, total=0
):
    processing_text = "_IN_PROCESS"
    course = get_course(course_id, instance=instance)
    completed_path_name = f"{course}_browser_data{format_instance_name(instance)}"
    completed_path = RESULTS / f"{completed_path_name}.csv"
    if completed_path.exists():
        print_task_complete_message(completed_path)
        return
    if verbose:
        echo(f"==== COURSE {index + 1:,} of {total:,} ====")
        echo(f") Fetching users for {color(course, 'blue')}...")
    print(completed_path)
    result_path = (
        completed_path.parent
        / f"{completed_path_name}{processing_text}{completed_path.suffix}"
    )
    users = collect(course.get_users(enrollment_type=["student"]))[:6]
    for index, user in enumerate(users):
        get_user_agents(user, result_path, index, len(users), verbose)
    with open(result_path) as result_file:
        results = reader(result_file)
        max_row_length = max([len(row) for row in results])
    columns = ["Canvas User ID", "Name", "Email"]
    number_of_user_agent_columns = max_row_length - len(columns)
    user_agent_columns = list()
    for index in range(1, number_of_user_agent_columns + 1):
        user_agent_columns.append(f"User Agent {index}")
    columns = columns + user_agent_columns
    with open(result_path) as result_file:
        rows = result_file.read()
    with open(result_path, "w") as result_file:
        writer(result_file).writerow(columns)
        result_file.write(rows)
    new_name = result_path.name.replace(processing_text, "")
    result_path.replace(result_path.parent / new_name)
    echo("COMPLETE")


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
