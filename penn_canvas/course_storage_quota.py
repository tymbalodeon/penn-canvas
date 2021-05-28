from datetime import datetime
from pathlib import Path

import pandas
import typer

from .canvas_shared import code_to_sis, get_canvas

TODAY = datetime.now().strftime("%d_%b_%Y")
STORAGE = Path.home() / "penn-canvas/storage"
REPORTS = STORAGE / "reports"
RESULTS = STORAGE / "results"
RESULT_PATH = RESULTS / f"{TODAY}.csv"
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
            f"\tCanvas storage reports directory not found. Creating one for you at: {REPORTS} "
            "Please add a Canvas storage report matching today's date to this directory and then run this script again. "
            "(If you need instructions for generating a Canvas storage report, run this command with the '--help' flag.)"
        )
        raise typer.Exit(1)
    else:
        TODAYS_REPORT = ""
        CSV_FILES = Path(REPORTS).glob("*.csv")

        for report in CSV_FILES:
            if TODAY in report.name:
                TODAYS_REPORT = report

        if TODAYS_REPORT == "":
            typer.echo(
                "\tA Canvas storage report matching today's date was not found. "
                f"Please add a Canvas storage report matching today's date to the following directory: {REPORTS} "
                "(If you need instructions for generating a Canvas storage report, run this command with the '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            return TODAYS_REPORT


def cleanup_report(report):
    typer.echo(") Removing unused columns...")
    UNUSED_COLUMNS = [
        "short name",
        "name",
        "account sis id",
        "account name",
        "sum of all files in MB",
    ]
    DATA = pandas.read_csv(report)

    for column in UNUSED_COLUMNS:
        if column in DATA:
            DATA.drop(
                [column],
                axis=1,
                inplace=True,
            )

    typer.echo(") Removing courses with 0 storage...")
    DATA.drop(DATA[DATA["storage used in MB"] == 0].index, inplace=True)
    DATA.sort_values(by=["storage used in MB"], inplace=True)
    DATA = DATA.astype("string", copy=False, errors="ignore")

    return DATA


def check_percent_storage(data, canvas, verbose=False, increase=1000, use_sis_id=False):
    typer.echo(") Checking percentage of storage used for each course...")
    COURSES_TO_RAISE = list()

    ROWS = data.itertuples(index=False)

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
                        f"- Canvas ID: {canvas_id} | SIS_ID: {sis_id} | Storage used: {storage_used} | Storage Quota (MB): {canvas_course.storage_quota_mb} | Percentage used: {percentage_display}"
                    )

                if percentage_used >= 0.79:
                    if pandas.isna(sis_id):
                        if verbose:
                            typer.echo(
                                f"\t* Storage for course with Canvas ID {canvas_id} needs to be increased. (NO SIS ID!)"
                            )
                    elif sis_id:
                        if verbose:
                            typer.echo(
                                f"\t* Storage for course with SIS ID {sis_id} needs to be increased"
                            )
                        COURSES_TO_RAISE.append(sis_id)
            except:
                if verbose:
                    typer.echo(f"\t* Couldn't find course with SIS ID: {sis_id}")

    if verbose:
        for row in ROWS:
            check_percentages(row)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for row in progress:
                check_percentages(row)

    return pandas.DataFrame({"sis_id": COURSES_TO_RAISE})


def raise_quota(data, canvas, verbose=False, increase=1000, use_sis_id=True):
    typer.echo(
        ") Raising course storage quotas for courses using 80% or more of their storage...\n"
    )

    if not RESULTS.exists():
        Path.mkdir(RESULTS)

    SUBACCOUNT = list()
    COURSE_ID = list()
    OLD_QUOTA = list()
    NEW_QUOTA = list()

    ROWS = data["sis_id"].tolist()

    def raise_course_quota(sis_id):
        if use_sis_id and sis_id[:4] != "SRS_":
            sis_id = code_to_sis(sis_id)

        try:
            canvas_course = canvas.get_course(
                sis_id,
                use_sis_id=use_sis_id,
            )
            SUBACCOUNT.append(canvas_course.account_id)
            COURSE_ID.append(sis_id)
        except:
            canvas_course = None
            SUBACCOUNT.append("ERROR")
            COURSE_ID.append(sis_id)

        if canvas_course:
            old_quota = canvas_course.storage_quota_mb
            new_quota = old_quota + increase

            try:
                canvas_course.update(course={"storage_quota_mb": new_quota})
                typer.echo(f"\nCourse ID {sis_id} old quota: {old_quota}\n")
                typer.echo(f"Course ID {sis_id} new quota: {new_quota}\n")
            except:
                new_quota = "ERROR"
                typer.echo(f"\tFailed to raise quota for Canvas course ID: {sis_id}")

            OLD_QUOTA.append(old_quota)
            NEW_QUOTA.append(new_quota)
        else:
            RESULT.write("N/A, N/A\n")
            OLD_QUOTA.append("N/A")
            NEW_QUOTA.append("N/A")

    if verbose:
        for sis_id in ROWS:
            raise_course_quota(sis_id)
    else:
        with typer.progressbar(ROWS, length=len(data.index)) as progress:
            for sis_id in progress:
                raise_course_quota(sis_id)

    ROWS = list(zip(SUBACCOUNT, COURSE_ID, OLD_QUOTA, NEW_QUOTA))
    RESULT = pandas.DataFrame(
        ROWS, columns=["subaccount_id", "course_id", "old_quota", "new_quota"]
    )
    RESULT.to_csv(RESULT_PATH, index=False)


def storage_main(test, verbose):
    REPORT = find_todays_report()
    CANVAS = get_canvas(test)
    CLEAN_REPORT = cleanup_report(REPORT)
    COURSES_TO_RAISE = check_percent_storage(CLEAN_REPORT, CANVAS, verbose)
    raise_quota(COURSES_TO_RAISE, CANVAS, verbose)
    typer.echo("FINISHED")
