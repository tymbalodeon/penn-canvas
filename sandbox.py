from canvasapi.course import Course
from canvasapi.section import Section
from canvasapi.user import User

from .api import (
    Instance,
    get_account,
    get_canvas,
    get_course,
    get_section,
    get_user,
    pprint,
)

CANVAS = get_canvas(verbose=False)
ACCOUNT = get_account(verbose=False)


def user(canvas_id, id_type=None, instance=Instance.PRODUCTION):
    return get_user(canvas_id, id_type, instance, verbose=True, pretty_print=True)


def course(course_id, use_sis_id=False, instance=Instance.PRODUCTION):
    get_course(course_id, use_sis_id, instance, verbose=True, pretty_print=True)


def section(section_id, use_sis_id=False, instance=Instance.PRODUCTION):
    get_section(section_id, use_sis_id, instance, verbose=True, pretty_print=True)


def enrollments(enrollment_container: Course | Section | User, first_only=False):
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
