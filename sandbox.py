from canvasapi.course import Course
from canvasapi.section import Section
from canvasapi.user import User

from penn_canvas.helpers import get_account, get_canvas, pprint

CANVAS = get_canvas(verbose=False)
ACCOUNT = get_account(verbose=False)


def get_user(user, id_type=None, instance="prod"):
    user = get_canvas(instance).get_user(user, id_type=id_type)
    pprint(user)
    return user


def get_course(course, use_sis_id=False, instance="prod"):
    course = get_canvas(instance).get_course(course, use_sis_id=use_sis_id)
    pprint(course)
    return course


def get_section(section, use_sis_id=False, instance="prod"):
    section = get_canvas(instance).get_section(section, use_sis_id=use_sis_id)
    pprint(section)
    return section


def get_enrollments(enrollment_container: Course | Section | User, first_only=False):
    if first_only:
        enrollments = next(
            (enrollment for enrollment in enrollment_container.get_enrollments()), None
        )
        pprint(enrollments)
    else:
        enrollments = [
            enrollment for enrollment in enrollment_container.get_enrollments()
        ]
        for enrollment in enrollments:
            pprint(enrollment)
    return enrollments


parameters = {"courses": True, "terms": "2022A"}
