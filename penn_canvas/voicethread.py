from typer import echo

from .helpers import MAIN_ACCOUNT_ID, color, get_canvas


def is_voicethread_assignments(assignment):
    try:
        return "voicethread" in assignment.external_tool_tag_attributes["url"]
    except Exception:
        return False


year_and_term = "2021C"
account_id = 99237
canvas = get_canvas()
account = canvas.get_account(account_id)
main_account = canvas.get_account(MAIN_ACCOUNT_ID)
term = next(
    (
        term.id
        for term in main_account.get_enrollment_terms()
        if year_and_term in term.name
    ),
    None,
)
courses = [course for course in account.get_courses(enrollment_term_id=term)]
courses_count = len(courses)


def voicethread_main():
    for index, course in enumerate(courses):
        assignments = [assignment for assignment in course.get_assignments()]
        assignments = [
            assignment
            for assignment in assignments
            if is_voicethread_assignments(assignment)
        ]
        voicethread_count = len(assignments)
        display_color = "green" if voicethread_count else "yellow"
        echo(
            f" - ({index + 1}/{courses_count}) {color(course.name)}:"
            f" {color(voicethread_count, display_color)}"
        )
