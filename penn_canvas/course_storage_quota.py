from datetime import datetime
from pathlib import Path

import pandas
import typer

from .canvas_shared import code_to_sis, get_canvas, get_command_paths

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS = get_command_paths("storage")
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}.csv"
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


def find_todays_report():
    typer.echo(") Finding today's report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        typer.echo(
            "\tCanvas storage reports directory not found. Creating one for you at:"
            f" {REPORTS}\n\tPlease add a Canvas storage report matching today's date to"
            " this directory and then run this script again.\n\t(If you need"
            " instructions for generating a Canvas storage report, run this command"
            " with the '--help' flag.)"
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
                "- Please add a Canvas storage report matching today's date"
                f" to the following directory: {REPORTS}\n- (If you need instructions"
                " for generating a Canvas storage report, run this command with the"
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
    data.drop(data[data["storage used in MB"] == 0].index, inplace=True)
    data.sort_values(by=["storage used in MB"], inplace=True)
    data = data.astype("string", copy=False, errors="ignore")

    return data


def check_percent_storage(data, canvas, verbose=False, increase=1000, use_sis_id=False):
    typer.echo(") Checking percentage of storage used for each course...")
    COURSES_TO_INCREASE = list()
    ROWS = data.itertuples(index=False)
    ERRORS = list()

    def check_percentages(row):
        canvas_id, sis_id, account_id, storage_used = row

        if account_id in SUB_ACCOUNTS:
            try:
                canvas_course = canvas.get_course(canvas_id)
                percentage_used = float(storage_used) / round(
                    int(canvas_course.storage_quota_mb)
                )
                if verbose:
                    percentage_display = typer.style(
                        f"{int(percentage_used * 100)}%",
                        fg=typer.colors.MAGENTA,
                    )
                    typer.echo(
                        f"- Canvas ID: {canvas_id}, SIS_ID: {sis_id}, Storage used:"
                        f" {storage_used}, Storage Quota (MB):"
                        f" {canvas_course.storage_quota_mb}, Percentage used:"
                        f" {percentage_display}"
                    )

                if percentage_used >= 0.79:
                    if verbose:
                        typer.secho("\t* Increase required", fg=typer.colors.YELLOW)
                    if pandas.isna(sis_id):
                        sis_id_error = (
                            "ACTION REQUIRED: A SIS_ID must be added for course:"
                            " {canvas_id}"
                        )
                        if verbose:
                            typer.secho(f"\t* {sis_id_error}", fg=typer.colors.YELLOW)
                        ERRORS.append(sis_id_error)
                    elif sis_id:
                        COURSES_TO_INCREASE.append(sis_id)
            except Exception:
                not_found_error = (
                    "Couldn't find course: Canvas ID: {canvas_id}, SIS ID: {sis_id}"
                )
                if verbose:
                    typer.secho("\t* {not_found_error}", fg=typer.colors.YELLOW)
                ERRORS.append(not_found_error)

    if verbose:
        for row in ROWS:
            check_percentages(row)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for row in progress:
                check_percentages(row)

    COURSES = pandas.DataFrame({"sis_id": COURSES_TO_INCREASE})

    return COURSES, ERRORS


def increase_quota(data, canvas, verbose=False, increase=1000):
    typer.echo(
        ") Increasing course storage quotas for courses using 80% or more of their"
        " storage..."
    )

    SUBACCOUNT = list()
    COURSE_ID = list()
    OLD_QUOTA = list()
    NEW_QUOTA = list()

    ROWS = data["sis_id"].tolist()

    def increase_course_quota(sis_id):
        if sis_id[:4] != "SRS_":
            sis_id = code_to_sis(sis_id)

        try:
            canvas_course = canvas.get_course(
                sis_id,
                use_sis_id=True,
            )
            SUBACCOUNT.append(canvas_course.account_id)
            COURSE_ID.append(sis_id)
        except Exception:
            canvas_course = None
            SUBACCOUNT.append("ERROR")
            COURSE_ID.append(sis_id)

        if canvas_course:
            old_quota = canvas_course.storage_quota_mb
            new_quota = old_quota + increase

            try:
                canvas_course.update(course={"storage_quota_mb": new_quota})
                if verbose:
                    typer.echo(
                        f"\t- {sis_id}, Old Quota: {old_quota}, New Quota: {new_quota}"
                    )
            except Exception:
                new_quota = "ERROR"
                if verbose:
                    typer.secho(
                        f"\t* Failed to increase quota for Canvas course ID: {sis_id}",
                        fg=typer.colors.YELLOW,
                    )

            OLD_QUOTA.append(old_quota)
            NEW_QUOTA.append(new_quota)
        else:
            RESULT.write("N/A, N/A\n")
            OLD_QUOTA.append("N/A")
            NEW_QUOTA.append("N/A")

    if verbose:
        for sis_id in ROWS:
            increase_course_quota(sis_id)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for sis_id in progress:
                increase_course_quota(sis_id)

    ROWS = list(zip(SUBACCOUNT, COURSE_ID, OLD_QUOTA, NEW_QUOTA))

    typer.echo(f") Saving results to {RESULT_PATH}...")

    if not RESULTS.exists():
        Path.mkdir(RESULTS)

    RESULT = pandas.DataFrame(
        ROWS, columns=["subaccount_id", "course_id", "old_quota", "new_quota"]
    )
    RESULT.to_csv(RESULT_PATH, index=False)

    return str(len(RESULT.index))


def print_errors(errors):
    for error in errors:
        typer.secho(f"- ERROR: {error}", fg=typer.colors.RED)


def storage_main(test, verbose):
    report = find_todays_report()
    report = cleanup_report(report)
    CANVAS = get_canvas(test)
    COURSES_TO_INCREASE, ERRORS = check_percent_storage(report, CANVAS, verbose)
    INCREASED_COURSE_NUMBER = increase_quota(COURSES_TO_INCREASE, CANVAS, verbose)
    STYLED_NUMBER = typer.style(INCREASED_COURSE_NUMBER, fg=typer.colors.MAGENTA)
    typer.echo(f"- Increased storage quota for {STYLED_NUMBER} courses.")
    if len(ERRORS) > 0:
        print_errors(ERRORS)
    typer.echo("FINISHED")
