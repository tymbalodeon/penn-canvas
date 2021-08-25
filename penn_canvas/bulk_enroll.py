from pathlib import Path

from pandas import DataFrame, to_csv
from typer import echo

from .helpers import MAIN_ACCOUNT_ID, get_canvas

SUBACCOUNT = 99241
TERMS = [
    5773,
    5799,
    5818,
    5833,
    5901,
    5910,
    5956,
    5988,
    6008,
    6055,
    6086,
    6112,
    6139,
    6269,
    6291,
    6304,
    6321,
    5688,
    5821,
    5911,
    6063,
    6120,
    6303,
    4373,
    2244,
]

USER = 5985383


def bulk_enroll_main(test, terms=TERMS, subaccount=SUBACCOUNT):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    ACCOUNT = CANVAS.get_account(MAIN_ACCOUNT_ID)
    COURSES = list()

    for term in TERMS:
        COURSES.extend(
            [
                course
                for course in ACCOUNT.get_courses(
                    enrollment_term_id=term, by_subaccounts=[SUBACCOUNT]
                )
            ]
        )

    course_codes = [
        course.sis_course_id if course.sis_course_id else course.name
        for course in COURSES
    ]

    courses = DataFrame(course_codes, columns=["course"])
    courses.to_csv(Path.home() / "Desktop" / "course_to_enroll.csv", index=False)

    for course in COURSES:
        try:
            enrollment = course.enroll_user(
                USER, enrollment={"enrollment_state": "active"}
            )
            echo(f"Enrolled: {enrollment}")
        except Exception:
            echo("failed to enroll")
