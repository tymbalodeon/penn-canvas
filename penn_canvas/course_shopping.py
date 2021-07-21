"""
~~~~~~~~~~~~ COURSE SHOPPING ~~~~~~~~~~~~~~~~
get a provisioning report of all courses
1. delete all columns but: canvas_id, sis_id, short_name, account_id, status
2. delete all rows with blank sis_ids
3. compare with master and remove and previously seen courses
4. create one file for WH (sis_id !startwith SRS_) and one for rest
5. run enable_course_shopping() on non wharton file
6. run WHARTON_enable_course_shopping() on wharton file
7. upload each file results to pennbox
8. add newly enabled to MASTER
9. upload new version of MASTER

"""

from datetime import datetime
from pathlib import Path

import pandas
import typer

from .helpers import (
    colorize_path,
    find_subaccounts,
    get_canvas,
    get_command_paths,
    make_csv_paths,
)

TESTING = False
TERM = "2021A"

TODAY = datetime.now().strftime("%d_%b_%Y")
TODAY_AS_Y_M_D = datetime.strptime(TODAY, "%d_%b_%Y").strftime("%Y_%m_%d")
REPORTS, RESULTS, LOGS = get_command_paths("shopping", True)
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_course_shopping_result.csv"
HEADERS = ["index", "canvas course id", "course id", "status", "notes"]

DISABLE_OUTFILE = (
    f"data/course_shopping_disabled_{TODAY}{'_test' if TESTING else ''}.csv"
)
WH_DISABLE_OUTFILE = (
    f"data/WH_course_shopping_disabled_{TODAY}{'_test' if TESTING else ''}.csv"
)
MASTER_FILE = f"data/course_shopping_master_{TERM}{'_test' if TESTING else ''}.csv"

canvas_id_in_master = []

SUB_ACCOUNT_EXCLUDE = "82603"
WH_EXCLUDE = [
    "1570395",
    "1561313",
    "1547534",
    "1570415",
    "1557428",
    "1561900",
    "1569679",
    "1570197",
    "1556491",
    "1568283",
    "1571450",
    "1569376",
    "1568956",
    "1571142",
    "1557429",
    "1569235",
    "1556348",
    "1568292",
    "1560829",
    "1562996",
    "1569378",
    "1561940",
    "1557344",
    "1561720",
    "1562001",
    "1570626",
    "1561675",
    "1562002",
    "1568363",
    "1568432",
    "1570977",
    "1569407",
    "1561254",
    "1560744",
    "1561759",
    "1570413",
    "1571335",
    "1571258",
    "1571346",
    "1567954",
    "1567952",
    "1567970",
    "1570982",
    "1571220",
    "1571223",
    "1571226",
    "1571259",
    "1571247",
    "1571213",
    "1571228",
    "1561671",
    "1561674",
    "1561001",
    "1571466",
    "1571465",
    "1571464",
    "1571262",
    "1571480",
    "1571482",
    "1571481",
    "1571479",
    "1569321",
    "1558823",
    "1571264",
    "1557348",
    "1569541",
    "1569542",
    "1560288",
    "1567879",
    "1557350",
    "1568926",
    "1569318",
    "1571265",
    "1571266",
    "1558648",
    "1561859",
    "1571246",
    "1569543",
    "1570202",
    "1570446",
    "1570717",
    "1570718",
    "1571252",
    "1571364",
    "1570301",
    "1556034",
    "1554947",
    "1568466",
    "1568827",
    "1561296",
    "1561297",
    "1561298",
    "1561299",
    "1561264",
    "1571251",
    "1568963",
    "1569346",
    "1571267",
    "1570668",
    "1568923",
    "1570600",
    "1562905",
    "1567756",
    "1568631",
    "1571469",
    "1560739",
    "1560996",
    "1568515",
    "1568517",
    "1568518",
    "1568520",
    "1568522",
    "1568524",
    "1568526",
    "1568528",
    "1568530",
    "1568532",
    "1568534",
    "1568536",
    "1568538",
    "1568540",
    "1568542",
    "1568544",
    "1568546",
    "1568548",
    "1568550",
    "1568552",
    "1568554",
    "1568556",
    "1568558",
    "1568560",
    "1568561",
    "1568516",
    "1568519",
    "1568521",
    "1568523",
    "1568525",
    "1568527",
    "1568529",
    "1568531",
    "1568533",
    "1568535",
    "1568537",
    "1568539",
    "1568541",
    "1568543",
    "1568545",
    "1568547",
    "1568549",
    "1568551",
    "1568553",
    "1568555",
    "1568557",
    "1568559",
    "1568562",
    "1568563",
    "1568564",
    "1568511",
    "1568512",
    "1568513",
    "1568514",
    "1568565",
    "1568566",
    "1568567",
    "1568568",
    "1568569",
    "1557340",
    "1557268",
    "1557336",
    "1557341",
    "1557338",
    "1561872",
    "1557337",
    "1569470",
    "1569471",
    "1569472",
    "1569473",
    "1569474",
    "1569475",
    "1569476",
    "1569477",
    "1569478",
    "1569479",
    "1569480",
    "1569481",
    "1569482",
    "1569483",
    "1569484",
    "1569485",
    "1569486",
    "1569487",
    "1569488",
    "1569489",
    "1569490",
    "1569491",
    "1569492",
    "1569493",
    "1569494",
    "1569495",
    "1569496",
    "1569497",
    "1569498",
    "1569499",
    "1569500",
    "1569501",
    "1569502",
    "1569503",
    "1569504",
    "1569505",
    "1569506",
    "1569507",
    "1569508",
    "1569509",
    "1569510",
    "1569511",
    "1569512",
    "1560922",
    "1571374",
    "1571375",
    "1571376",
    "1571377",
    "1571378",
    "1571379",
    "1571380",
    "1571387",
    "1571381",
    "1571382",
    "1571383",
    "1571384",
    "1571388",
    "1571385",
    "1571386",
    "1569548",
]

SAS_ONL_ACCOUNT = "132413"
ADMIN_ACCOUNT = "131963"
WHARTON_ACCOUNT_ID = "81471"
SAS_ACCOUNT_ID = "99237"
SEAS_ACCOUNT_ID = "99238"
NURS_ACCOUNT_ID = "99239"
AN_ACCOUNT_ID = "99243"
IGNORED_SUBJECTS = ["MAPP", "IMPA", "DYNM"]
IGNORED_SITES = ["1529220"]


def get_accounts(test):
    canvas = get_canvas(test)
    SEAS_ACCOUNTS = find_subaccounts(canvas, SEAS_ACCOUNT_ID)
    NURS_ACCOUNTS = find_subaccounts(canvas, NURS_ACCOUNT_ID)
    SAS_ACCOUNTS = find_subaccounts(canvas, SAS_ACCOUNT_ID)
    SAS_ACCOUNTS.remove(SAS_ONL_ACCOUNT)
    SAS_ACCOUNTS.remove(ADMIN_ACCOUNT)
    AN_ACCOUNTS = find_subaccounts(canvas, AN_ACCOUNT_ID)

    return SEAS_ACCOUNTS, NURS_ACCOUNTS, SAS_ACCOUNTS, AN_ACCOUNTS


def find_course_shopping_report():
    typer.echo(") Finding Canvas Provisioning (Courses) report...")

    if not REPORTS.exists():
        Path.mkdir(REPORTS, parents=True)
        error = typer.style(
            "- ERROR: Canvas course shopping reports directory not found.",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            f"{error} \n- Creating one for you at: {colorize_path(str(REPORTS))}\n-"
            " Please add a Canvas Provisioning (Courses) report matching today's date to"
            " this directory and then run this script again.\n- (If you need"
            " instructions for generating a Canvas Provisioning report, run this"
            " command with the '--help' flag.)"
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
                "- ERROR: A Canvas Provisioning (Courses) CSV report matching today's date"
                " was not found.",
                fg=typer.colors.YELLOW,
            )
            typer.echo(
                "- Please add a Canvas Provisioning (Courses) report matching today's date"
                " to the following directory and then run this script again:"
                f" {colorize_path(str(REPORTS))}\n- (If you need instructions for"
                " generating a Canvas Provisioning report, run this command with the"
                " '--help' flag.)"
            )
            raise typer.Exit(1)
        else:
            return TODAYS_REPORT


def cleanup_report(report, start=0):
    typer.echo(") Preparing report...")

    data = pandas.read_csv(report)
    data = data[
        ["canvas_course_id", "course_id", "short_name", "canvas_account_id", "status"]
    ]
    data = data.astype("string", copy=False)
    data = data[data["course_id"] != ""]
    data.reset_index(drop=True, inplace=True)

    TOTAL = len(data.index)
    data = data.loc[start:TOTAL, :]

    return data, str(TOTAL)


def course_contains_srs(course_id):
    return course_id.startswith("SRS_")


def section_contains_srs(canvas, canvas_id):
    course = canvas.get_course(canvas_id)
    sections = course.get_sections()

    srs_section = next(
        filter(lambda section: section.sis_section_id.startswith("SRS_"), sections),
        None,
    )

    return bool(srs_section)


def load_master():
    master = open(MASTER_FILE, "r")
    master.readline()

    for line in master:
        sis_id, canvas_id, visibility_status, published, notes = line.strip().split(",")
        if visibility_status.strip() == "public_to_auth_users":
            canvas_id_in_master.append(canvas_id.strip())

    master.close()


def should_update_course(canvas_account_id, course_number, subject, test):
    SEAS_ACCOUNTS, NURS_ACCOUNTS, SAS_ACCOUNTS, AN_ACCOUNTS = get_accounts(test)

    if (
        canvas_account_id in SEAS_ACCOUNTS
        or (canvas_account_id in NURS_ACCOUNTS and course_number <= 600)
        or (
            canvas_account_id in SAS_ACCOUNTS
            and course_number <= 500
            and subject not in IGNORED_SUBJECTS
        )
        or (
            canvas_account_id in AN_ACCOUNTS
            and course_number <= 500
            and subject == "COMM"
        )
    ):

        return True
    else:
        return False


def enable_course_shopping(courses, wharton, test):
    typer.echo(") Enabling course shopping for non-Wharton schools...")
    canvas = get_canvas(TESTING)
    WHARTON_ACCOUNTS = find_subaccounts(canvas, WHARTON_ACCOUNT_ID)
    SEAS_ACCOUNTS, NURS_ACCOUNTS, SAS_ACCOUNTS, AN_ACCOUNTS = get_accounts(test)
    SUB_ACCOUNTS = SAS_ACCOUNTS + SEAS_ACCOUNTS + NURS_ACCOUNTS + AN_ACCOUNTS
    courses = courses[
        "index", "canvas course id", "course id", "canvas_account_id", "status"
    ]

    for course in courses.itertuples():
        (
            index,
            canvas_course_id,
            course_id,
            canvas_account_id,
            status,
        ) = course

        if canvas_course_id in canvas_id_in_master:
            continue

        if wharton:
            account = WHARTON_ACCOUNTS
            srs_checker = section_contains_srs
            course_or_section_string = "section"
            ignored_courses = SUB_ACCOUNT_EXCLUDE
        else:
            account = SUB_ACCOUNTS
            srs_checker = course_contains_srs
            course_or_section_string = "course"
            ignored_courses = IGNORED_SITES

        if canvas_account_id not in account:
            typer.echo("- School not participating.")
            notes = "school not participating"
        elif not course_contains_srs(course_id):
            typer.echo(f"- {course_or_section_string} not in SRS.")
            notes = f"{course_or_section_string} not in srs"
        elif canvas_course_id in IGNORED_SITES:
            typer.echo("- Ignored course.")
            notes = "ignored course"
        else:
            try:
                canvas_course = canvas.get_course(canvas_course_id)
                course_number = int(course_id.split("-")[1])
                subject = course_id.split("-")[0][4:]
                notes = ""

                if wharton or should_update_course(
                    canvas_account_id, course_number, subject, test
                ):
                    typer.echo(f") Updating course...")

                    canvas_course.update(course={"is_public_to_auth_users": True})
                    status = "public to auth users"
                elif subject in IGNORED_SUBJECTS:
                    typer.echo("- Ignored course.")
                    notes = "ignored course"
            except Exception as error:
                typer.echo(
                    f"- ERROR: Failed to enable course shopping for {canvas_course_id} - {course_id} ({error})"
                )
                status = "ERROR"
                notes = error

        courses.loc[
            index,
            [
                "canvas_course_id",
                "course_id",
                "status",
                "notes",
            ],
        ] = [canvas_course_id, course_id, status, notes]

        courses.to_csv(RESULT_PATH)


def disable_course_shopping(inputfile=MASTER_FILE, outputfile=DISABLE_OUTFILE):
    canvas = get_canvas(TESTING)

    dataFile = open(inputfile, "r")
    dataFile.readline()

    outFile = open(outputfile, "w+")
    outFile.write("sis_id, canvas_id, visibility_status, published, notes\n")

    forWH = False

    if "WH_" in inputfile:
        forWH = True

    for line in dataFile:
        sis_id, canvas_id, visibility_status, published, notes = line.replace(
            "\n", ""
        ).split(",")

        if (not forWH and visibility_status.strip() == "public_to_auth_users") or (
            forWH and "NOT WHARTON" not in notes
        ):
            try:
                canvas_course = canvas.get_course(canvas_id)
                canvas_course.update(
                    course={
                        "is_public": False,
                        "is_public_to_auth_users": False,
                        "public_syllabus": False,
                        "public_syllabus_to_auth": False,
                    }
                )
                status = "disabled"

            except Exception as ex:
                notes = "Exception: %s" % (ex)
                status = "Exception"

            print(sis_id, canvas_id, status, published, notes)
            outFile.write(
                "%s, %s, %s, %s, %s\n" % (sis_id, canvas_id, status, published, notes)
            )


def shopping_main(wharton, test):
    INSTANCE = "test" if test else "prod"
    CANVAS = get_canvas(INSTANCE)
    report = find_course_shopping_report()
    report, TOTAL = cleanup_report(report)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    enable_course_shopping(report, wharton, test)
    typer.echo("FINISHED")


# load_master()
# print(canvas_id_in_master)

# WHARTON_enable_course_shopping(INFILE, WH_OUTFILE)
# print("WHARTON completed")

# enable_course_shopping(INFILE, OUTFILE)
# print("All completed")

# disable_course_shopping(MASTER_FILE, DISABLE_OUTFILE)
# disable_course_shopping(WH_OUTFILE, WH_DISABLE_OUTFILE)
