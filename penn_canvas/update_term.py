from penn_canvas.style import print_item

from .api import (
    Instance,
    format_instance_name,
    get_account,
    get_enrollment_term_id,
    validate_instance_name,
)
from .helpers import color, get_command_paths

COMMAND_NAME = "Update Terms"
RESULTS = get_command_paths(COMMAND_NAME)["results"]
HEADERS = [
    "canvas course id",
    "course id",
    "course name",
    "account",
    "old term",
    "new term",
]


def update_term_main(
    account_id: int, current_term: str, new_term: str, instance_name: str | Instance
):
    instance = validate_instance_name(instance_name)
    account = get_account(account_id, instance=instance)
    current_term_id = get_enrollment_term_id(current_term, account)
    new_term_id = get_enrollment_term_id(new_term, account)
    instance_name = format_instance_name(instance)
    results_path = (
        RESULTS / f"{account}_update_{current_term}_to_{new_term}{instance_name}.csv"
    )
    courses = [
        course for course in account.get_courses(enrollment_term_id=current_term_id)
    ]
    if not results_path.exists():
        with open(results_path, "w") as results_file:
            results_file.write(",".join(HEADERS))
    total = len(courses)
    for index, course in enumerate(courses):
        row = [
            str(course.id),
            str(course.sis_course_id),
            course.name.replace(",", "_"),
            str(course.account_id),
            f"{current_term} ({course.enrollment_term_id})",
        ]
        try:
            course.update(course={"term_id": new_term_id})
            row.append(f"{new_term} ({new_term_id})")
            message = (
                f"Updated {color(course, 'yellow')} with enrollment term"
                f" {color(new_term, 'blue')}"
            )
        except Exception as error:
            row.append(f"ERROR: {error}")
            message = (
                "ERROR: Failed to update"
                f" {color(course, 'yellow')} ({color(error, 'red')})"
            )
        print_item(index, total, message)
        with open(results_path, "a") as results_file:
            results_file.write("\n")
            results_file.write(",".join(row))
