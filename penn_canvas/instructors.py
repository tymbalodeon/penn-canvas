from pathlib import Path

from pandas import DataFrame, read_csv

from penn_canvas.api import get_course, get_user
from penn_canvas.style import print_item


def get_names_and_emails(path: Path):
    courses = read_csv(path)
    total = len(courses.index)
    rows = list()
    for (
        index,
        canvas_course_id,
        course_id,
        course_name,
        account,
        term,
        status,
        turnitin_assingments,
        published_turnitin_assingments,
    ) in courses.itertuples():
        course = get_course(canvas_course_id)
        print_item(index, total, str(course))
        teachers = list(course.get_enrollments(type="TeacherEnrollment"))
        total_teachers = len(teachers)
        for teacher_index, teacher in enumerate(teachers):
            print_item(teacher_index, total_teachers, str(teacher))
            name = teacher.user["name"]
            email = get_user(teacher.user_id).email
            row = [
                canvas_course_id,
                course_id,
                course_name,
                account,
                term,
                status,
                turnitin_assingments,
                published_turnitin_assingments,
                name,
                email,
            ]
            rows.append(row)
    columns = [
        "canvas course id",
        "course id",
        "course name",
        "account",
        "term",
        "status",
        "turnitin assignments",
        "published turnitin assignments",
        "name",
        "email",
    ]
    results = DataFrame(rows, columns=columns)
    results = results.drop_duplicates(subset="email")
    results.to_csv(Path.home() / "Desktop/results.csv", index=False)
