from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from canvasapi.enrollment import Enrollment as CanvasEnrollment
from click.utils import echo
from pandas.io.parsers.readers import read_csv
from pytz import utc

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
    get_start_index,
    make_csv_paths,
    print_skip_message,
    print_task_complete_message,
    switch_logger_file,
    writerow,
)
from .style import color, print_item

COMMAND_PATH = create_directory(BASE_PATH / "Check Enrollment")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")
HEADERS = ["index", "Date Enrolled", "Name", "Email"]


@dataclass
class Enrollment:
    name: str
    email: str
    date_enrolled: str


def get_email(user_id: int, instance: Instance) -> str:
    return next(
        (
            channel.address
            for channel in get_user(
                user_id, instance=instance
            ).get_communication_channels()
            if channel.type == "email"
        ),
        "",
    )


def format_date_enrolled(date: datetime) -> str:
    return date.strftime("%Y-%m-%d")


def get_enrollment(
    canvas_enrollment: CanvasEnrollment,
    result_path: Path,
    instance: Instance,
    start,
    index,
    total,
    verbose,
) -> Enrollment:
    name = canvas_enrollment.user["name"]
    email = get_email(canvas_enrollment.user_id, instance)
    date_enrolled = format_date_enrolled(canvas_enrollment.created_at_date)
    index = index + start
    if verbose:
        date_display = color(date_enrolled, "cyan")
        name_display = color(name, "yellow")
        message = f"{date_display}: {name_display}"
        print_item(index, total, message)
    row = [index, date_enrolled, name, email]
    writerow(result_path, row, "a")
    return Enrollment(name, email, date_enrolled)


def check_enrollment_main(
    course_id: int, date: str, instance_name: str | Instance, force: bool, verbose: bool
):
    instance = validate_instance_name(instance_name, verbose=verbose)
    switch_logger_file(LOGS, "check_enrollment", instance.name)
    start_date = utc.localize(datetime.strptime(date, "%Y-%m-%d"))
    course = get_course(course_id, instance=instance)
    instance_display = format_instance_name(instance)
    result_path_string = f"{course}_enrollments_after_{date}{instance_display}.csv"
    result_path = RESULTS / result_path_string
    start = get_start_index(force, result_path)
    print_skip_message(start, "enrollments")
    make_csv_paths(result_path, HEADERS)
    if verbose:
        echo(") Getting enrollments...")
    enrollments = [
        enrollment
        for enrollment in course.get_enrollments()
        if enrollment.created_at_date > start_date
    ]
    enrollments = sorted(enrollments, key=lambda enrollment: enrollment.created_at_date)
    if verbose:
        echo(f"{color(course)} enrollments after {color(date, 'cyan')}: ")
    total = len(enrollments)
    enrollments = [
        get_enrollment(enrollment, result_path, instance, start, index, total, verbose)
        for index, enrollment in enumerate(enrollments[start:])
    ]
    results = read_csv(result_path)
    results.drop("index", axis=1, inplace=True)
    results.to_csv(result_path, index=False)
    print_task_complete_message(result_path)
