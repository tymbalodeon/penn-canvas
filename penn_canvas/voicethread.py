from typer import echo

from .helpers import MAIN_ACCOUNT_ID, color, get_canvas, get_command_paths


def is_turnitin_assignment(assignment):
    try:
        if "url" in assignment.external_tool_tag_attributes:
            return "turnitin" in assignment.external_tool_tag_attributes["url"]
        else:
            return False
    except Exception:
        return False


def is_voicethread_assignment(assignment):
    try:
        return "voicethread" in assignment.external_tool_tag_attributes["url"]
    except Exception:
        return False


COMMAND = "Count Tool Usage"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]
HEADERS = [
    "canvas course id",
    "course id",
    "course name",
    "account",
    "term",
    "status",
]
terms = ["A", "B", "C"]
year_and_terms = [f"2021{term}" for term in terms]
account_id = 99237


def get_courses(term, main_account, account):
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


def voicethread_main(tool):
    canvas = get_canvas()
    main_account = canvas.get_account(MAIN_ACCOUNT_ID)
    account = canvas.get_account(account_id)
    for term in year_and_terms:
        results_path = RESULTS / f"{term}_{tool}_usage.csv"
        if tool == "turnitin":
            headers = HEADERS + [
                "turnitin assignments",
                "published turnitin assignemnts",
            ]
        else:
            headers = HEADERS + ["voicethread assignments"]
        if not results_path.exists():
            with open(results_path, "w") as results_file:
                results_file.write(",".join(headers))
        courses = get_courses(term, main_account, account)
        courses_count = len(courses)
        for index, course in enumerate(courses):
            assignments = [assignment for assignment in course.get_assignments()]
            published_count = ""
            if tool == "turnitin":
                assignments = [
                    assignment
                    for assignment in assignments
                    if is_turnitin_assignment(assignment)
                ]
                published = [
                    assignment for assignment in assignments if assignment.published
                ]
                published_count = len(published)
            else:
                assignments = [
                    assignment
                    for assignment in assignments
                    if is_voicethread_assignment(assignment)
                ]
            count = len(assignments)
            account_object = canvas.get_account(course.account_id)
            row = [
                course.id,
                course.sis_course_id,
                course.name,
                account_object,
                term,
                course.workflow_state,
                count,
            ]
            if tool == "turnitin":
                row.append(published_count)
            row = [str(item).replace(",", "-") for item in row]
            with open(results_path, "a") as results_file:
                results_file.write("\n")
                results_file.write(",".join(row))
            display_color = "green" if count else "yellow"
            echo(
                f" - ({index + 1}/{courses_count}) {color(course.name)}:"
                f" {color(count, display_color)}"
            )
