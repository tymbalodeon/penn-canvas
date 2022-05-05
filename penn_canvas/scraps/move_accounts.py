from pathlib import Path

from pandas import read_csv

from penn_canvas.api import get_course, validate_instance_name
from penn_canvas.style import print_item


def move_accounts(courses_file: Path, new_account_id=99237, instance_name="test"):
    instance = validate_instance_name(instance_name)
    courses = read_csv(courses_file)["canvas_course_id"].tolist()
    total = len(courses)
    for index, course_id in enumerate(courses):
        course = get_course(course_id, instance=instance)
        update_values = {"account_id": new_account_id}
        updated = course.update(course=update_values)
        print_item(index, total, f"{course}: {'TRUE' if updated else 'ERROR'}")
