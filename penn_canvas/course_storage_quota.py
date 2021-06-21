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
    make_csv_paths,
    toggle_progress_bar,
)

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS = get_command_paths("storage")
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_storage_result.csv"
HEADERS = ["subaccount id", "course id", "old quota", "new quota", "error"]
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
    data.reset_index(drop=True, inplace=True)

    TOTAL = len(data.index)

    return data, TOTAL


def check_percent_storage(course, canvas, verbose, total):
    index, canvas_id, sis_id, account_id, storage_used = course
    index += 1

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

            typer.echo(
                f"- {sis_id} ({canvas_id}): {percentage_display} ({index}/{total})"
            )

        if percentage_used >= 0.79:
            if verbose:
                typer.secho("\t* INCREASE REQUIRED", fg=typer.colors.YELLOW)
            if pandas.isna(sis_id):
                if verbose:
                    message = typer.style(
                        "- ACTION REQUIRED: A SIS ID must be added for course:"
                        f" {canvas_id}",
                        fg=typer.colors.YELLOW,
                    )
                    typer.echo(f"{message} ({index}/{total})")
                return False, "missing sis id"
            elif sis_id:
                return True, sis_id
        else:
            return False, None
    except Exception:
        if verbose:
            message = typer.style(
                f"- ERROR: {sis_id} ({canvas_id}) NOT FOUND",
                fg=typer.colors.RED,
            )
            typer.echo(f"{message} ({index}/{total})")
        return False, "course not found"


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
        error = "none"
    except Exception:
        canvas_course = None
        subaccount_id = "ERROR"
        error = "course not found"

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

    ROW = [subaccount_id, sis_id, old_quota, new_quota, error]

    with open(RESULT_PATH, "a", newline="") as result:
        writer(result).writerow(ROW)


def write_error(sis_id, error):
    ROW = ["ERROR", sis_id, "N/A", "N/A", error]

    with open(RESULT_PATH, "a", newline="") as result:
        writer(result).writerow(ROW)


def process_result(result):
    increased_count = len(result[result["error"] == "none"].index)
    error_count = len(result[result["error"] != "none"].index)
    if error_count == 0:
        result.drop(columns=["error"], inplace=True)
        result.to_csv(RESULT_PATH, index=False)
    return increased_count, error_count


def print_messages(total, increased, errors):
    typer.echo("SUMMARY:")
    typer.echo(f"- Processed {colorize(str(total))} courses.")
    typer.echo(f"- Increased storage quota for {colorize(str(increased))} courses.")
    if errors > 0:
        typer.echo(f"- Failed to find {colorize(str(errors))} courses.")
    typer.echo("FINISHED")


def storage_main(test, verbose):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    report = find_storage_report()
    report, TOTAL = cleanup_report(report)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)

    def check_and_increase_storage(course, canvas, verbose, total):
        needs_increase, message = check_percent_storage(course, canvas, verbose, total)
        if needs_increase:
            increase_quota(message, canvas, verbose)
        if message == "course not found":
            sis_id = course[1]
            write_error(sis_id, message)

    typer.echo(") Processing courses...")
    toggle_progress_bar(
        report, check_and_increase_storage, CANVAS, verbose, options=TOTAL, index=True
    )
    RESULT = pandas.read_csv(RESULT_PATH)
    INCREASED_COUNT, ERROR_COUNT = process_result(RESULT)
    print_messages(TOTAL, INCREASED_COUNT, ERROR_COUNT)
