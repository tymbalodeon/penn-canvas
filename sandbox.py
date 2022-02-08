from pprint import PrettyPrinter

from canvasapi.course import Course
from canvasapi.section import Section
from canvasapi.user import User

from penn_canvas.helpers import MAIN_ACCOUNT_ID, get_canvas

pretty_printer = PrettyPrinter()


def get_account(account, use_sis_id=False, instance="prod"):
    account = get_canvas(instance).get_account(
        account if account else MAIN_ACCOUNT_ID, use_sis_id=use_sis_id
    )
    pretty_printer.pprint(vars(account))
    return account


def get_user(user, id_type=None, instance="prod"):
    user = get_canvas(instance).get_user(user, id_type=id_type)
    pretty_printer.pprint(vars(user))
    return user


def get_course(course, use_sis_id=False, instance="prod"):
    course = get_canvas(instance).get_course(course, use_sis_id=use_sis_id)
    pretty_printer.pprint(vars(course))
    return course


def get_section(section, use_sis_id=False, instance="prod"):
    section = get_canvas(instance).get_section(section, use_sis_id=use_sis_id)
    pretty_printer.pprint(vars(section))
    return section


def get_enrollments(enrollment_container: Course | Section | User, first=False):
    if first:
        enrollments = next(
            (enrollment for enrollment in enrollment_container.get_enrollments()), None
        )
        pretty_printer.pprint(vars(enrollments))
    else:
        enrollments = [
            enrollment for enrollment in enrollment_container.get_enrollments()
        ]
        for enrollment in enrollments:
            pretty_printer.pprint(vars(enrollment))
    return enrollments
