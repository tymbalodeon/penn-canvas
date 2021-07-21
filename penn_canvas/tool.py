from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    colorize_path,
    get_canvas,
    get_command_paths,
    get_start_index,
    make_csv_paths,
    make_skip_message,
    toggle_progress_bar,
)

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS = get_command_paths("tool")
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_email_result.csv"
HEADERS = ["index", "canvas user id", "email status", "supported school(s)"]

schools = {}

output = open("data/piazza_report.csv", "a")
output.write("Term\tCourse\tSchool\n")


def find_course_reports():
    typer.echo(") Finding Canvas Provisioning (Courses) report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = typer.style(
            "- ERROR: Canvas tool reports directory not found.", fg=typer.colors.YELLOW
        )
        typer.echo(
            f"{error} \n- Creating one for you at: {colorize_path(str(REPORTS))}\n-"
            " Please add a Canvas Provisioning (Courses) report matching today's date"
            " to this directory and then run this script again.\n- (If you need"
            " instructions for generating a Canvas Provisioning report, run this"
            " command with the '--help' flag.)"
        )

        raise typer.Exit(1)
    else:
        CSV_FILES = Path(REPORTS).glob("*.csv")
        TODAYS_REPORTS = filter(lambda file: TODAY in file.name, CSV_FILES)

        if not len(TODAYS_REPORTS):
            error = typer.style(
                "- ERROR: Canvas Provisioning (Courses) CSV reports matching today's"
                " date were not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                f"{error}\n- Please add a Canvas (Courses) Provisioning report for at"
                " least one term and matching today's date to the following directory"
                f" and then run this script again: {colorize_path(str(REPORTS))}\n- (If"
                " you need instructions for generating a Canvas Provisioning report,"
                " run this command with the '--help' flag.)"
            )

            raise typer.Exit(1)
        else:
            return TODAYS_REPORTS


def cleanup_report(report, start=0):
    typer.echo(") Preparing report...")

    data = pandas.read_csv(report)
    data = data[
        [
            "canvas_course_id",
            "course_id",
            "canvas_account_id",
            "term_id",
            "status",
        ]
    ]
    data.drop_duplicates(inplace=True)
    data = data.astype("string", copy=False)
    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def tool_main(tool, test, verbose, force):
    def check_tool_usage(course, canvas, verbose):
        try:
            (
                canvas_course_id,
                course_id,
                canvas_account_id,
                term_id,
                status,
            ) = course

            if course_id and status == "active":
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()
                tool_tab = next(filter(lambda tab: tab.label == tool, tabs), None)

                if (
                    tool_tab
                    and tool_tab.visibility == "public"
                    and canvas_account_id not in schools.keys()
                ):
                    account = canvas.get_account(canvas_account_id)
                    school = account.name
                    schools[canvas_account_id] = school

                    print(f"{course_id}, {term_id}, {school}")
                    output.write(f"{course_id}\t{term_id}\t{school}\n")
        except Exception as error:
            print(f"ERROR: {error} {course}")

    reports = find_course_reports()
    START = get_start_index(force, RESULT_PATH)
    reports, TOTAL = cleanup_report(reports, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    typer.echo(") Processing courses...")

    toggle_progress_bar(reports, check_tool_usage, CANVAS, verbose, index=True)

    typer.echo(START)
