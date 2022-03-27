from datetime import datetime

from pytz import UTC
from typer import echo, prompt

from .api import (
    Instance,
    format_instance_name,
    get_course,
    get_user,
    validate_instance_name,
)
from .helpers import (
    BASE_PATH,
    create_directory,
    make_csv_paths,
    print_task_complete_message,
    writerow,
)
from .style import color, print_item

COMMAND_PATH = create_directory(BASE_PATH / "Check Enrollment")
RESULTS = create_directory(COMMAND_PATH / "Results")
HEADERS = ["Name", "Email", "Date Enrolled"]


def get_valid_instance(instance):
    if instance.lower() in {"prod", "test", "open", "open_test"}:
        return instance
    else:
        echo("- ERROR: Invalid Canvas instance.")
        instance = prompt(
            'Please specify one of the following: "prod", "test", "open", "open_test"'
        )
        return get_valid_instance(instance)


def get_valid_date(year, month, day):
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except Exception:
        echo("- ERROR: Invalid date values. Please try again.")
        year = prompt("Please enter the year as YYYY")
        month = prompt("Please enter the month as M or MM (Do not use leading zeros.)")
        day = prompt("Please enter the day as D or DD (Do not use leading zeros.)")

        return get_valid_date(year, month, day)


def get_enrolled_at_date(enrollment):
    return enrollment[2]


def check_enrollment_main(
    course_id: int, year: int, month: int, day: int, instance_name: str | Instance
):
    start_date = get_valid_date(year, month, day)
    instance = validate_instance_name(instance_name)
    course = get_course(course_id, instance=instance)
    result_path_string = (
        f"{format_instance_name(instance)}_{course}_enrollments_after"
        "_{start_date.strftime('%Y_%m_%d')}.csv"
    )
    result_path = RESULTS / result_path_string
    make_csv_paths(result_path, HEADERS)
    enrollments = [
        [enrollment.user["name"], enrollment.user_id, enrollment.created_at_date]
        for enrollment in course.get_enrollments()
        if enrollment.created_at_date > start_date
    ]
    enrollments = sorted(enrollments, key=get_enrolled_at_date)
    for index, user in enumerate(enrollments):
        name, user_id, date_enrolled = user
        date_enrolled = date_enrolled.strftime("%Y-%m-%d")
        email = next(
            channel
            for channel in get_user(
                user_id, instance=instance
            ).get_communication_channels()
            if channel.type == "email"
        )
        user[1] = email
        writerow(result_path, [name, email, date_enrolled], "a")
        message = (
            f"{color(name, 'green')} enrolled in {color(course)} on"
            f" {color(date_enrolled, 'yellow')}."
        )
        print_item(index, len(enrollments), message)
        echo(
            f"{color(name, 'green')} enrolled in {color(course)} on"
            f" {color(date_enrolled, 'yellow')}."
        )
    print_task_complete_message(result_path)
