from typer import echo

from .api import Instance, get_account, get_main_account_id, validate_instance_name
from .style import color


def is_grad_course(course_number, graduate_course_minimum_number):
    return course_number >= graduate_course_minimum_number


def get_course_number(sis_course_id, year_and_term):
    try:
        sis_course_id = sis_course_id.replace(year_and_term, "")
        sis_course_id = "".join(
            character for character in sis_course_id if character.isdigit()
        )
        return int(sis_course_id[:3])
    except Exception:
        return False


def get_main_sections(sis_course_ids, year_and_term):
    echo(") Filtering out main sections...")
    course_numbers = set()
    for sis_course_id in sis_course_ids:
        if sis_course_id in course_numbers:
            sis_course_ids.remove(sis_course_id)
        else:
            course_numbers.add(sis_course_id)
    return {
        sis_course_id
        for sis_course_id in sis_course_ids
        if get_course_number(sis_course_id, year_and_term)
    }


def print_summary(summary):
    echo(color("SUMMARY", "yellow"))
    echo(summary)
    echo(color("FINISHED", "yellow"))


def count_sites_main(
    year_and_term: str,
    separate: bool,
    graduate_course_minimum_number: int,
    instance_name: str | Instance,
):
    instance = validate_instance_name(instance_name)
    account = get_account(get_main_account_id(instance))
    term = next(
        (
            term.id
            for term in account.get_enrollment_terms()
            if year_and_term in term.name
        ),
        None,
    )
    echo(f') Finding course codes for term "{color(year_and_term, "blue")}"...')
    sis_course_ids = [
        course.sis_course_id for course in account.get_courses(enrollment_term_id=term)
    ]
    sis_course_ids = get_main_sections(sis_course_ids, year_and_term)
    if separate:
        echo(") Separating undergraduate from graduate courses...")
        undergraduate_courses = [
            sis_course_id
            for sis_course_id in sis_course_ids
            if not is_grad_course(
                get_course_number(sis_course_id, year_and_term),
                graduate_course_minimum_number,
            )
        ]
        graduate_courses = [
            sis_course_id
            for sis_course_id in sis_course_ids
            if is_grad_course(
                get_course_number(sis_course_id, year_and_term),
                graduate_course_minimum_number,
            )
        ]
        summary = (
            f"- Number of unique {color(year_and_term, 'blue')} undergraduate course"
            " numbers with a Canvas site:"
            f" {color(len(undergraduate_courses), 'magenta')}\n- Number of unique"
            f" {color(year_and_term, 'blue')} graduate course numbers with a Canvas"
            f" site: {color(len(graduate_courses), 'magenta')}"
        )
    else:
        summary = (
            f"- Number of unique {color(year_and_term, 'blue')} course numbers with"
            f" a Canvas site: {color(len(sis_course_ids), 'magenta')}\n"
        )
    print_summary(summary)
