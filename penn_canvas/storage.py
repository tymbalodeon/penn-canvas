from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    colorize,
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
REPORTS, RESULTS = get_command_paths("storage")
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_storage_result.csv"
HEADERS = [
    "index",
    "id",
    "sis id",
    "account id",
    "storage used in MB",
    "old quota",
    "new quota",
    "error",
]
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
            f"{error} \n- Creating one for you at:"
            f" {colorize_path(str(REPORTS))}\n- Please add a Canvas storage report"
            " matching today's date to this directory and then run this script"
            " again.\n- (If you need instructions for generating a Canvas storage"
            " report, run this command with the '--help' flag.)"
        )

        raise typer.Exit(1)
    else:
        TODAYS_REPORT = ""
        CSV_FILES = Path(REPORTS).glob("*.csv")

        for report in CSV_FILES:
            if TODAY in report.name:
                TODAYS_REPORT = report

        if not TODAYS_REPORT:
            error = typer.style(
                "- ERROR: A Canvas Course Storage report matching today's date was not"
                " found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                f"{error}\n- Please add a Canvas storage report matching today's date"
                " to the following directory and then run this script again:"
                f" {colorize_path(str(REPORTS))}\n- (If you need instructions for"
                " generating a Canvas storage report, run this command with the"
                " '--help' flag.)"
            )

            raise typer.Exit(1)
        else:
            return TODAYS_REPORT


def cleanup_report(report, start=0):
    typer.echo(") Preparing report...")

    data = pandas.read_csv(report)
    data = data[["id", "sis id", "account id", "storage used in MB"]]
    data = data[data["storage used in MB"] > 0]
    data.sort_values(by=["storage used in MB"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")
    data = data[data["account id"].isin(SUB_ACCOUNTS)]
    data.reset_index(drop=True, inplace=True)
    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, TOTAL


def check_percent_storage(course, canvas, verbose, total):
    index, canvas_id, sis_id, account_id, storage_used = course

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
                f"- ({index + 1}/{total}) {sis_id} ({canvas_id}): {percentage_display}"
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
                    typer.echo(f"({index + 1}/{total}) {message}")

                return False, "missing sis id"
            else:
                return True, sis_id
        else:
            return False, None
    except Exception:
        if verbose:
            message = typer.style(
                f"ERROR: {sis_id} ({canvas_id}) NOT FOUND",
                fg=typer.colors.RED,
            )
            typer.echo(f"- ({index + 1}/{total}) {message}")
        return False, "course not found"


def increase_quota(sis_id, canvas, verbose, increase):
    if sis_id[:4] != "SRS_":
        middle = sis_id[:-5][-6:]
        sis_id = f"SRS_{sis_id[:11]}-{middle[:3]}-{middle[3:]} {sis_id[-5:]}"

    try:
        canvas_course = canvas.get_course(
            sis_id,
            use_sis_id=True,
        )
        subaccount_id = str(canvas_course.account_id)
        error = "none"
    except Exception:
        canvas_course = None
        subaccount_id = "ERROR"
        error = "course not found"

    if canvas_course:
        old_quota = canvas_course.storage_quota_mb
        new_quota = old_quota + increase
        old_quota = str(int(old_quota))
        new_quota = str(int(new_quota))

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

    return [subaccount_id, sis_id, old_quota, new_quota, error]


def process_result():
    result = pandas.read_csv(RESULT_PATH)
    increased_count = len(result[result["error"] == "none"].index)
    result.drop(result[result["error"] == "increase not required"].index, inplace=True)
    error_count = len(result[result["error"] != "none"].index)

    if error_count == 0:
        result.drop(columns=["error"], inplace=True)

    result.fillna("N/A", inplace=True)
    result.drop(columns=["index", "account id", "storage used in MB"], inplace=True)
    result.rename(columns={"id": "subaccount id", "sis id": "course id"}, inplace=True)
    result.to_csv(RESULT_PATH, index=False)

    return increased_count, error_count


def print_messages(total, increased, errors):
    typer.secho("SUMMARY:", fg=typer.colors.YELLOW)
    typer.echo(f"- Processed {colorize(str(total))} courses.")
    typer.echo(f"- Increased storage quota for {colorize(str(increased))} courses.")

    if errors > 0:
        message = typer.style(
            f"Failed to find {str(errors)} courses.", fg=typer.colors.RED
        )
        typer.echo(f"- {message}")

    typer.secho("FINISHED", fg=typer.colors.YELLOW)


def storage_main(test, verbose, force, increase=1000):
    def check_and_increase_storage(course, canvas, verbose, args):
        index = course[0]
        canvas_id = course[1]
        sis_id = course[2]
        total, increase = args

        needs_increase, message = check_percent_storage(course, canvas, verbose, total)

        if needs_increase:
            row = increase_quota(message, canvas, verbose, increase)
        elif message is None:
            row = [canvas_id, sis_id, "N/A", "N/A", "increase not required"]
        else:
            row = ["ERROR", sis_id, "N/A", "N/A", message]

        report.loc[
            index,
            [
                "id",
                "sis id",
                "old quota",
                "new quota",
                "error",
            ],
        ] = row
        report.loc[index].to_frame().T.to_csv(RESULT_PATH, mode="a", header=False)

    report = find_storage_report()
    START = get_start_index(force, RESULT_PATH)
    report, TOTAL = cleanup_report(report, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "course")
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)

    typer.echo(") Processing courses...")

    toggle_progress_bar(
        report,
        check_and_increase_storage,
        CANVAS,
        verbose,
        args=(TOTAL, increase),
        index=True,
    )
    INCREASED_COUNT, ERROR_COUNT = process_result()
    print_messages(TOTAL, INCREASED_COUNT, ERROR_COUNT)
