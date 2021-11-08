from csv import writer
from datetime import datetime

from pytz import UTC
from typer import echo, prompt

from .helpers import color, get_canvas, get_command_paths, make_csv_paths

COMMAND = "Check Enrollment"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]
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


def check_enrollment_main(course_id, year, month, day, instance):
    start_date = get_valid_date(year, month, day)
    INSTANCE = get_valid_instance(instance)
    CANVAS = get_canvas(INSTANCE)
    course = CANVAS.get_course(course_id)
    RESULT_PATH_STRING = (
        f"{INSTANCE.upper()}_{course}_enrollments_after"
        "_{start_date.strftime('%Y_%m_%d')}.csv"
    )
    RESULT_PATH = RESULTS / RESULT_PATH_STRING
    make_csv_paths(
        RESULTS,
        RESULT_PATH,
        HEADERS,
    )
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
            for channel in CANVAS.get_user(user_id).get_communication_channels()
            if channel.type == "email"
        )
        user[1] = email

        with open(RESULT_PATH, "a", newline="") as output_file:
            writer(output_file).writerow([name, email, date_enrolled])

        echo(
            f"- ({(index + 1):,}/{len(enrollments)}) {color(name, 'green')} enrolled"
            f" in {color(course)} on {color(date_enrolled, 'yellow')}."
        )

    echo("FINISHED")
