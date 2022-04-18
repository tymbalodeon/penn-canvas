from pathlib import Path

from pandas.core.frame import DataFrame

from penn_canvas.api import get_enrollment_term_id
from penn_canvas.style import print_item
from sandbox import ACCOUNT


def check_ares_tabs():
    term_id = get_enrollment_term_id("202220")
    courses = list(ACCOUNT.get_courses(enrollment_term_id=term_id))
    data = list()
    total = len(courses)
    for index, course in enumerate(courses):
        tab = next(
            (
                tab
                for tab in course.get_tabs()
                if tab.label == "Course Materials @ Penn Libraries"
            ),
            None,
        )
        if tab:
            visibility = tab.visibility
            try:
                hidden = tab.hidden
            except Exception:
                hidden = False
        else:
            visibility = "N/A"
            hidden = "N/A"
        data.append(
            [
                course.id,
                course.sis_course_id,
                course.name,
                tab,
                visibility,
                hidden,
            ]
        )
        message = f"{tab}: {visibility} {hidden}"
        print_item(index, total, message)
    data = DataFrame(
        data,
        columns=[
            "Course ID",
            "SIS Course ID",
            "Course Name",
            "Has Ares Tab",
            "Visibility",
            "Hidden",
        ],
    )
    data.to_csv(Path.home() / "Desktop/output.csv", index=False)
