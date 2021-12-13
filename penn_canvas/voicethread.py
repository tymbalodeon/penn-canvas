from typer import echo

from .helpers import MAIN_ACCOUNT_ID, color, get_canvas, get_command_paths


def is_voicethread_assignments(assignment):
    try:
        return "voicethread" in assignment.external_tool_tag_attributes["url"]
    except Exception:
        return False


COMMAND = "Count Voicethread"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]
HEADERS = [
    "canvas course id",
    "course id",
    "short name",
    "account id",
    "term id",
    "status",
    "voicethread assignments",
]
terms = ["A", "B", "C"]
year_and_terms = [f"2021{term}" for term in terms]
account_id = 99237
canvas = get_canvas()
account = canvas.get_account(account_id)
main_account = canvas.get_account(MAIN_ACCOUNT_ID)


def get_courses(term):
    enrollment_term_id = next(
        (
            enrollment_term.id
            for enrollment_term in main_account.get_enrollment_terms()
            if term in enrollment_term.name
        ),
        None,
    )
    return [
        course for course in account.get_courses(enrollment_term_id=enrollment_term_id)
    ]


def voicethread_main():
    for term in year_and_terms:
        results_path = RESULTS / f"{term}_voicethread_usage.csv"
        if not results_path.exists():
            with open(results_path, "w") as results_file:
                results_file.write(",".join(HEADERS))
        courses = get_courses(term)
        courses_count = len(courses)
        for index, course in enumerate(courses):
            assignments = [assignment for assignment in course.get_assignments()]
            assignments = [
                assignment
                for assignment in assignments
                if is_voicethread_assignments(assignment)
            ]
            voicethread_count = len(assignments)
            account_name = canvas.get_account(course.account_id).name
            row = [
                course.id,
                course.sis_course_id,
                course.name,
                account_name,
                term,
                course.workflow_state,
                voicethread_count,
            ]
            row = [str(item).replace(",", "-") for item in row]
            with open(results_path, "a") as results_file:
                results_file.write("\n")
                results_file.write(",".join(row))
            display_color = "green" if voicethread_count else "yellow"
            echo(
                f" - ({index + 1}/{courses_count}) {color(course.name)}:"
                f" {color(voicethread_count, display_color)}"
            )
