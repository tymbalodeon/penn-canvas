from datetime import datetime

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


def check_enrollment_main(course_id: int, date: str, instance_name: str | Instance):
    instance = validate_instance_name(instance_name)
    start_date = datetime.strptime(date, "%Y-%m-%d")
    course = get_course(course_id, instance=instance)
    instance_display = format_instance_name(instance)
    result_path_string = f"{course}_enrollments_after_{date}{instance_display}.csv"
    result_path = RESULTS / result_path_string
    make_csv_paths(result_path, HEADERS)
    enrollments = [
        {
            "name": enrollment.user["name"],
            "user_id": enrollment.user_id,
            "created_at_date": enrollment.created_at_date,
        }
        for enrollment in course.get_enrollments()
        if enrollment.created_at_date > start_date
    ]
    enrollments = sorted(
        enrollments, key=lambda enrollment: enrollment["created_at_date"]
    )
    total = len(enrollments)
    for index, user in enumerate(enrollments):
        name = user["name"]
        email = next(
            channel
            for channel in get_user(
                user["user_id"], instance=instance
            ).get_communication_channels()
            if channel.type == "email"
        )
        date_enrolled = user["created_at_date"].strftime("%Y-%m-%d")
        writerow(result_path, [name, email, date_enrolled], "a")
        name_display = color(name, "green")
        course_display = color(course)
        enrollment_display = color(date_enrolled, "yellow")
        message = (
            f"{name_display} enrolled in {course_display} on {enrollment_display}."
        )
        print_item(index, total, message)
    print_task_complete_message(result_path)
