from typer import echo

from penn_canvas.helpers import (
    MAIN_ACCOUNT_ID,
    PREVIOUS_YEAR_AND_TERM,
    color,
    get_canvas,
    get_command_paths,
)

COMMAND = "Update Terms"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]
HEADERS = [
    "canvas course id",
    "course id",
    "course name",
    "account",
    "old term",
    "new term",
]


def update_term_main(account_id, current_term, new_term, test):
    if not current_term:
        term = "".join(
            [character for character in PREVIOUS_YEAR_AND_TERM if character.isalpha()]
        )
        term_string = {"A": "Spring", "B": "Summer", "C": "Fall"}.get(term)
        year = "".join(
            [character for character in PREVIOUS_YEAR_AND_TERM if character.isnumeric()]
        )
        current_term = f"{PREVIOUS_YEAR_AND_TERM} ({term_string} {year})"
    INSTANCE = "test" if test else "prod"
    canvas = get_canvas(INSTANCE)
    main_account = canvas.get_account(MAIN_ACCOUNT_ID)
    enrollment_terms = [
        enrollment_term for enrollment_term in main_account.get_enrollment_terms()
    ]
    current_term_id = next(
        (
            enrollment_term.id
            for enrollment_term in enrollment_terms
            if enrollment_term.name == current_term
            or enrollment_term.id == current_term
        ),
        None,
    )
    new_term_id = next(
        (
            enrollment_term.id
            for enrollment_term in enrollment_terms
            if enrollment_term.name == new_term or enrollment_term.id == new_term
        ),
        None,
    )
    account = canvas.get_account(account_id)
    courses = [
        course for course in account.get_courses(enrollment_term_id=current_term_id)
    ]
    results_path = (
        RESULTS
        / f"{account}_update_{current_term}_to_{new_term}_{'test' if test else ''}.csv"
    )
    if not results_path.exists():
        with open(results_path, "w") as results_file:
            results_file.write(",".join(HEADERS))
    for index, course in enumerate(courses):
        row = [
            str(course.id),
            str(course.sis_course_id),
            course.name.replace(",", "_"),
            str(course.account_id),
            f"{current_term} ({course.enrollment_term_id})",
        ]
        try:
            course.update(course={"term_id": new_term_id})
            row.append(f"{new_term} ({new_term_id})")
            echo(
                f"- ({index + 1:,}/{len(courses):,}) Updated"
                f" {color(course, 'yellow')} with enrollment term"
                f" {color(new_term, 'blue')}"
            )
        except Exception as error:
            row.append(f"ERROR: {error}")
            echo(
                f"- ({index + 1:,}/{len(courses):,}) ERROR: Failed to update"
                f" {color(course, 'yellow')} ({color(error, 'red')})"
            )
        with open(results_path, "a") as results_file:
            results_file.write("\n")
            results_file.write(",".join(row))
