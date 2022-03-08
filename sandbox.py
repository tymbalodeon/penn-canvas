from pprint import PrettyPrinter

from canvasapi.course import Course
from canvasapi.section import Section
from canvasapi.user import User

from penn_canvas.helpers import MAIN_ACCOUNT_ID, get_canvas


def pprint(thing):
    if isinstance(thing, list):
        for item in thing[:5]:
            PrettyPrinter().pprint(vars(item))
    else:
        PrettyPrinter().pprint(vars(thing))


def collect(paginator):
    return [item for item in paginator]


def get_account(account, use_sis_id=False, instance="prod"):
    account = get_canvas(instance).get_account(
        account if account else MAIN_ACCOUNT_ID, use_sis_id=use_sis_id
    )
    pprint(account)
    return account


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
