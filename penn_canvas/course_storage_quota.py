from csv import writer
from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    colorize,
    colorize_path,
    get_canvas,
    get_command_paths,
    make_results_paths,
    toggle_progress_bar,
)

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS = get_command_paths("storage")
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_storage_result.csv"
HEADERS = ["subaccount id", "course id", "old quota", "new quota"]
SUB_ACCOUNTS = [
    "132477",
    "99243",
    "99237",
    "132280",
    "107448",
    "132413",
    "128877",
    "99241",
    "99244",
    "99238",
    "99239",
    "131752",
    "131428",
    "99240",
    "132153",
    "82192",
]


def find_storage_report():
    typer.echo(") Finding storage report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = typer.style(
            "- ERROR: Canvas storage reports directory not found.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"{error} \n- Creating one for you at: {colorize_path(REPORTS)}\n\tPlease"
            " add a Canvas storage report matching today's date to this directory and"
            " then run this script again.\n- (If you need instructions for generating"
            " a Canvas storage report, run this command with the '--help' flag.)"
        )
        raise typer.Exit(1)
    else:
        TODAYS_REPORT = ""
        CSV_FILES = Path(REPORTS).glob("*.csv")

        for report in CSV_FILES:
            if TODAY in report.name:
                TODAYS_REPORT = report

        if not TODAYS_REPORT:
            typer.secho(
                "- ERROR: A Canvas Course Storage report matching today's date was not"
                " found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                "- Please add a Canvas storage report matching today's date to the"
                " following directory and then run this script again:"
                f" {colorize_path(str(REPORTS))}\n- (If you need instructions for"
                " generating a Canvas storage report, run this command with the"
                " '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            return TODAYS_REPORT


def cleanup_report(report):
    typer.echo(") Removing unused columns...")
    data = pandas.read_csv(report)
    data = data[["id", "sis id", "account id", "storage used in MB"]]

    typer.echo(") Removing courses with 0 storage...")
    data = data[data["storage used in MB"] > 0]
    data.sort_values(by=["storage used in MB"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")
    data = data[data["account id"].isin(SUB_ACCOUNTS)]

    return data


def check_percent_storage(course, canvas, verbose):
    canvas_id, sis_id, account_id, storage_used = course

    try:
        canvas_course = canvas.get_course(canvas_id)
        percentage_used = float(storage_used) / canvas_course.storage_quota_mb

        if verbose:
            if percentage_used >= 0.79:
                percentage_display = typer.style(
                    f"{int(percentage_used * 100)}%", fg=typer.colors.YELLOW
                )
            else:
                percentage_display = typer.style(
                    f"{int(percentage_used * 100)}%", fg=typer.colors.GREEN
                )

            typer.echo(f"- {sis_id} ({canvas_id}): {percentage_display}")

        if percentage_used >= 0.79:
            if verbose:
                typer.secho("\t* INCREASE REQUIRED", fg=typer.colors.YELLOW)
            if pandas.isna(sis_id):
                sis_id_error = (
                    f"ACTION REQUIRED: A SIS_ID must be added for course: {canvas_id}"
                )
                if verbose:
                    typer.secho(f"\t* {sis_id_error}", fg=typer.colors.YELLOW)
                return False, sis_id_error
            elif sis_id:
                return True, sis_id
        else:
            return False, None
    except Exception:
        not_found_error = f"ERROR: {sis_id} ({canvas_id}) NOT FOUND"
        if verbose:
            typer.secho(f"- {not_found_error}", fg=typer.colors.RED)
        return False, not_found_error


def increase_quota(sis_id, canvas, verbose, increase=1000):
    if sis_id[:4] != "SRS_":
        middle = sis_id[:-5][-6:]
        sis_id = f"SRS_{sis_id[:11]}-{middle[:3]}-{middle[3:]} {sis_id[-5:]}"

    try:
        canvas_course = canvas.get_course(
            sis_id,
            use_sis_id=True,
        )
        subaccount_id = canvas_course.account_id
    except Exception:
        canvas_course = None
        subaccount_id = "ERROR"

    if canvas_course:
        old_quota = canvas_course.storage_quota_mb
        new_quota = old_quota + increase

        try:
            canvas_course.update(course={"storage_quota_mb": new_quota})
            if verbose:
                typer.echo(
                    f"\t* Increased storage from {old_quota} MB to {new_quota} MB"
                )
        except Exception:
            new_quota = "ERROR"
            if verbose:
                typer.secho(
                    f"\t* Failed to increase quota for Canvas course ID: {sis_id}",
                    fg=typer.colors.YELLOW,
                )

    else:
        old_quota = "N/A"
        new_quota = "N/A"

    ROW = [subaccount_id, sis_id, old_quota, new_quota]

    with open(RESULT_PATH, "a", newline="") as result:
        writer(result).writerow(ROW)


def print_errors(errors):
    for error in errors:
        typer.secho(f"- ERROR: {error}", fg=typer.colors.RED)


def storage_main(test, verbose):
    CANVAS = get_canvas(test)
    report = find_storage_report()
    report = cleanup_report(report)
    make_results_paths(RESULTS, RESULT_PATH, HEADERS)
    ERRORS = list()

    def check_and_increase_storage(course, canvas, verbose):
        needs_increase, message = check_percent_storage(course, canvas, verbose)
        if needs_increase:
            increase_quota(message, canvas, verbose)
        elif message is not None:
            ERRORS.append(message)

    typer.echo(") Processing courses...")
    toggle_progress_bar(report, check_and_increase_storage, CANVAS, verbose)
    RESULT = pandas.read_csv(RESULT_PATH)
    INCREASED = len(RESULT.index)
    typer.echo(f"- Increased storage quota for {colorize(str(INCREASED))} courses.")
    typer.echo("FINISHED")
