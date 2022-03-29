from typing import Optional

from penn_canvas.style import print_item

from .api import (
    Instance,
    format_instance_name,
    get_account,
    get_enrollment_term_id,
    get_main_account_id,
    validate_instance_name,
)
from .helpers import color, get_command_paths, make_csv_paths, write

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
    account_id: Optional[int],
    current_term_name: str,
    new_term_name: str,
    instance_name: str | Instance,
):
    instance = validate_instance_name(instance_name)
    if not account_id:
        account_id = get_main_account_id(instance)
    account = get_account(account_id, instance=instance)
    current_term_id = get_enrollment_term_id(current_term_name, account)
    new_term_id = get_enrollment_term_id(new_term_name, account)
    instance_name = format_instance_name(instance)
    results_path = (
        RESULTS
        / f"{account}_update_{current_term_name}_to_{new_term_name}{instance_name}.csv"
    )
    courses = [
        course for course in account.get_courses(enrollment_term_id=current_term_id)
    ]
    make_csv_paths(results_path, HEADERS)
    total = len(courses)
    for index, course in enumerate(courses):
        row = [
            str(course.id),
            str(course.sis_course_id),
            course.name.replace(",", "_"),
            str(course.account_id),
            f"{current_term_name} ({course.enrollment_term_id})",
        ]
        try:
            course.update(course={"term_id": new_term_id})
            row.append(f"{new_term_name} ({new_term_id})")
            message = (
                f"Updated {color(course, 'yellow')} with enrollment term"
                f" {color(new_term_name, 'blue')}"
            )
        except Exception as error:
            row.append(f"ERROR: {error}")
            message = (
                "ERROR: Failed to update"
                f" {color(course, 'yellow')} ({color(error, 'red')})"
            )
        print_item(index, total, message)
        write(results_path, f"\n{','.join(row)}", "a")
