from pathlib import Path

from pandas import DataFrame
from tqdm import tqdm
from typer import Exit, echo
from ua_parser import user_agent_parser

from .helpers import get_canvas
from .style import color, print_item


def get_user_account_data(user):
    return [user.id, user.name, user.email]


def parse_user_agent_string(user_agent_string):
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


def get_user_agents(index, total, user):
    echo(f") Fetching user agents for {color(user)}...")
    user_agents = {
        parse_user_agent_string(page_view.user_agent)
        for page_view in tqdm(user.get_page_views())
        if page_view.user_agent
    }
    message = (
        f"{color(user.name)} used {color(len(user_agents), 'yellow')} different agents."
    )
    print_item(index, total, message)
    return list(user_agents)


def fill_empty_columns(data_list, total_columns):
    if len(data_list) < total_columns:
        return data_list + ([None] * (total_columns - len(data_list)))
    else:
        return data_list


def browser_main(courses, instance):
    if not courses:
        echo("No courses provided.")
        raise Exit()

    canvas = get_canvas(instance)
    total_courses = len(courses)
    result_path = Path.home() / "Desktop" / "results.csv"
    for index, course in enumerate(courses):
        echo(f"==== COURSE {index + 1:,} of {total_courses:,} ====")
        course = canvas.get_course(course)
        echo(f") Fetching users for {color(course, 'blue')}...")
        users = [user for user in course.get_users(enrollment_type=["student"])]
        total_users = len(users)
        users = [
            get_user_account_data(user) + get_user_agents(index, total_users, user)
            for index, user in enumerate(users)
        ]
        columns = ["Canvas User ID", "Name", "Email"]
        number_of_user_agent_columns = max({len(user) for user in users}) - len(columns)
        columns = columns + ["User Agent"] * number_of_user_agent_columns
        users = [fill_empty_columns(user, len(columns)) for user in users]
        users = DataFrame(users, columns=columns)
        users.to_csv(result_path, index=False)
