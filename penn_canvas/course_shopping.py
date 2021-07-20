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

import typer
from .helpers import find_subaccounts, get_canvas

TESTING = False
TERM = "2021A"

TIME = datetime.now().strftime("%d_%b_%Y")

INFILE = f"data/course_shopping_{TIME}{'_test' if TESTING else ''}.csv"
OUTFILE = f"data/course_shopping_enabled_{TIME}{'_test' if TESTING else ''}.csv"
WH_OUTFILE = f"data/WH_course_shopping_enabled_{TIME}{'_test' if TESTING else ''}.csv"
DISABLE_OUTFILE = (
    f"data/course_shopping_disabled_{TIME}{'_test' if TESTING else ''}.csv"
)
WH_DISABLE_OUTFILE = (
    f"data/WH_course_shopping_disabled_{TIME}{'_test' if TESTING else ''}.csv"
)
MASTER_FILE = f"data/course_shopping_master_{TERM}{'_test' if TESTING else ''}.csv"

canvas_id_in_master = []

WH_EXCLUDE = (
    1570395,
    1561313,
    1547534,
    1570415,
    1557428,
    1561900,
    1569679,
    1570197,
    1556491,
    1568283,
    1571450,
    1569376,
    1568956,
    1571142,
    1557429,
    1569235,
    1556348,
    1568292,
    1560829,
    1562996,
    1569378,
    1561940,
    1557344,
    1561720,
    1562001,
    1570626,
    1561675,
    1562002,
    1568363,
    1568432,
    1570977,
    1569407,
    1561254,
    1560744,
    1561759,
    1570413,
    1571335,
    1571258,
    1571346,
    1567954,
    1567952,
    1567970,
    1570982,
    1571220,
    1571223,
    1571226,
    1571259,
    1571247,
    1571213,
    1571228,
    1561671,
    1561674,
    1561001,
    1571466,
    1571465,
    1571464,
    1571262,
    1571480,
    1571482,
    1571481,
    1571479,
    1569321,
    1558823,
    1571264,
    1557348,
    1569541,
    1569542,
    1560288,
    1567879,
    1557350,
    1568926,
    1569318,
    1571265,
    1571266,
    1558648,
    1561859,
    1571246,
    1569543,
    1570202,
    1570446,
    1570717,
    1570718,
    1571252,
    1571364,
    1570301,
    1556034,
    1554947,
    1568466,
    1568827,
    1561296,
    1561297,
    1561298,
    1561299,
    1561264,
    1571251,
    1568963,
    1569346,
    1571267,
    1570668,
    1568923,
    1570600,
    1562905,
    1567756,
    1568631,
    1571469,
    1560739,
    1560996,
    1568515,
    1568517,
    1568518,
    1568520,
    1568522,
    1568524,
    1568526,
    1568528,
    1568530,
    1568532,
    1568534,
    1568536,
    1568538,
    1568540,
    1568542,
    1568544,
    1568546,
    1568548,
    1568550,
    1568552,
    1568554,
    1568556,
    1568558,
    1568560,
    1568561,
    1568516,
    1568519,
    1568521,
    1568523,
    1568525,
    1568527,
    1568529,
    1568531,
    1568533,
    1568535,
    1568537,
    1568539,
    1568541,
    1568543,
    1568545,
    1568547,
    1568549,
    1568551,
    1568553,
    1568555,
    1568557,
    1568559,
    1568562,
    1568563,
    1568564,
    1568511,
    1568512,
    1568513,
    1568514,
    1568565,
    1568566,
    1568567,
    1568568,
    1568569,
    1557340,
    1557268,
    1557336,
    1557341,
    1557338,
    1561872,
    1557337,
    1569470,
    1569471,
    1569472,
    1569473,
    1569474,
    1569475,
    1569476,
    1569477,
    1569478,
    1569479,
    1569480,
    1569481,
    1569482,
    1569483,
    1569484,
    1569485,
    1569486,
    1569487,
    1569488,
    1569489,
    1569490,
    1569491,
    1569492,
    1569493,
    1569494,
    1569495,
    1569496,
    1569497,
    1569498,
    1569499,
    1569500,
    1569501,
    1569502,
    1569503,
    1569504,
    1569505,
    1569506,
    1569507,
    1569508,
    1569509,
    1569510,
    1569511,
    1569512,
    1560922,
    1571374,
    1571375,
    1571376,
    1571377,
    1571378,
    1571379,
    1571380,
    1571387,
    1571381,
    1571382,
    1571383,
    1571384,
    1571388,
    1571385,
    1571386,
    1569548,
)


SAS_ONL_ACCOUNT = 132413
ADMIN_ACCOUNT = 131963
WHARTON_ACCOUNT_ID = 81471
SAS_ACCOUNT_ID = 99237
SEAS_ACCOUNT_ID = 99238
NURS_ACCOUNT_ID = 99239
AN_ACCOUNT_ID = 99243
IGNORED_SUBJECTS = ["MAPP", "IMPA", "DYNM"]
IGNORED_SITES = ["1529220"]


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


def enable_wharton_course_shopping(inputfile, outputfile):
    canvas = get_canvas(TESTING)

    WHARTON_ACCOUNT_ID = 81471
    WHARTON_ACCOUNTS = find_subaccounts(canvas, WHARTON_ACCOUNT_ID)
    SUB_ACCOUNT_EXCLUDE = 82603

    dataFile = open(inputfile, "r")
    dataFile.readline()

    outFile = open(outputfile, "w+")
    outFile.write("sis_id, canvas_id, visibility_status, published, notes\n")

    for line in dataFile:
        canvas_id, sis_id, short_name, account_id, status = line.replace(
            "\n", ""
        ).split(",")

        if len(sis_id) > 0 and canvas_id not in canvas_id_in_master:
            notes = ""
            canvas_course = None

            try:
                canvas_course = canvas.get_course(canvas_id)
                published = status
            except:
                notes = "couldnt find course"
                published = "ERROR"

            if canvas_course:
                if not account_id.isnumeric():
                    print("\t Invalid account_id %s", account_id)
                elif (
                    int(account_id) not in WHARTON_ACCOUNTS
                ):  # then we should not update this site!!!!
                    print("\t school not participating")
                    notes += "/ NOT WHARTON"
                    outFile.write(
                        "%s, %s, %s, %s, %s\n"
                        % (sis_id, canvas_id, status, published, notes)
                    )

                else:  # account id in WHARTON_ACCOUNTS
                    update = False
                    try:
                        # see if the course is connected to SRS
                        print("\t", canvas_id, sis_id, short_name, account_id, status)
                        update = False

                        in_SRS = section_contains_srs(canvas, canvas_id)
                        if in_SRS == False:
                            print("\t not in SRS")
                            notes += "\ not liked to SRS"
                            update = False
                        elif (
                            int(canvas_id) in WH_EXCLUDE
                            or account_id == SUB_ACCOUNT_EXCLUDE
                        ):
                            print("\t single site to ignore")
                            notes += "\ in exclude list"
                            update = False
                        else:  # we know the course is connected to SRS and not a special ignore site
                            update = True
                    except:
                        print("ERROR WITH COURSE: ", sis_id, canvas_id)
                        outFile.write(
                            "%s, %s, %s, %s, %s\n"
                            % (sis_id, canvas_id, "err", "err", "err")
                        )

                    if update:
                        print("\t\tshould update course")
                        try:
                            canvas_course.update(
                                course={"is_public_to_auth_users": True}
                            )
                            status = "public_to_auth_users"
                        except:
                            status = "ERROR"

                        print(sis_id, canvas_id, status, published, notes)

                    outFile.write(
                        "%s, %s, %s, %s, %s\n"
                        % (sis_id, canvas_id, status, published, notes)
                    )

                    # add this line to master file
                    master = open(MASTER_FILE, "a")
                    master.write(
                        "%s, %s, %s, %s, %s\n"
                        % (sis_id, canvas_id, status, published, notes)
                    )
                    master.close()
        """

                # NEED TO SWAP ALL THE FALSES TO TRUES
                # Check if in Wharton
                if int(account_id) in WHARTON_ACCOUNTS:
                    # check if linked to SRS -- use helper function
                    in_SRS = linked_to_SRS(course_id)
                    # STILL NEED TO MAKE CASE FOR EXECUTIVE MBA
                    if in_SRS == True: 
                        update = True
                else:
                    #CHeck if course's sections are associated with SRS (
        """

    dataFile.close()
    outFile.close()


def enable_course_shopping(courses, outputfile):
    canvas = get_canvas(TESTING)

    WHARTON_ACCOUNTS = find_subaccounts(canvas, WHARTON_ACCOUNT_ID)
    SAS_ACCOUNTS = find_subaccounts(canvas, SAS_ACCOUNT_ID)
    SAS_ACCOUNTS.remove(SAS_ONL_ACCOUNT)
    SAS_ACCOUNTS.remove(ADMIN_ACCOUNT)
    SEAS_ACCOUNTS = find_subaccounts(canvas, SEAS_ACCOUNT_ID)
    NURS_ACCOUNTS = find_subaccounts(canvas, NURS_ACCOUNT_ID)
    AN_ACCOUNTS = find_subaccounts(canvas, AN_ACCOUNT_ID)
    SUB_ACCOUNTS = SAS_ACCOUNTS + SEAS_ACCOUNTS + NURS_ACCOUNTS + AN_ACCOUNTS

    dataFile = open(courses, "r")
    dataFile.readline()

    outFile = open(outputfile, "w+")
    outFile.write("sis_id, canvas_id, visibility_status, published, notes\n")

    for course in courses.itertuples():
        index, canvas_id, sis_id, short_name, account_id, status = course

        if len(sis_id) > 0 and canvas_id not in canvas_id_in_master:

            notes = ""
            canvas_course = None

            try:
                canvas_course = canvas.get_course(canvas_id)
                published = status
            except Exception:
                notes = "couldnt find course"
                published = "ERROR"

            if canvas_course:
                if not account_id.isnumeric():
                    print(f"- ERROR: Invalid account id: {account_id}")
                elif int(account_id) not in SUB_ACCOUNTS:
                    print("- School not participating")
                    notes += "/ subaccount opt out"
                    outFile.write(
                        f"{sis_id}, {canvas_id}, {status}, {published}, {notes}"
                    )
                else:
                    try:
                        update = False

                        if not course_contains_srs(sis_id):
                            print("- Course not in SRS.")
                        elif int(canvas_id) in IGNORED_SITES:
                            print("- Ignored course.")
                        else:
                            course_number = sis_id.split("-")[1]
                            subject = sis_id.split("-")[0][4:]
                            print(f"- COURSE NUMBER: {course_number}")
                            print(f"- SUBJECT: {subject}")

                            if int(account_id) in SEAS_ACCOUNTS:
                                update = True
                            else:
                                if int(account_id) in NURS_ACCOUNTS:
                                    if int(course_number) <= 600:
                                        update = True
                                elif (
                                    int(account_id) in SAS_ACCOUNTS
                                    and int(course_number) <= 500
                                ):
                                    if subject in IGNORED_SUBJECTS:
                                        print("- Ignored subject.")
                                    else:
                                        update = True
                                elif (
                                    int(account_id) in AN_ACCOUNTS
                                    and int(course_number) <= 500
                                ):
                                    if subject == "COMM":
                                        update = True
                    except Exception as error:
                        print(
                            f"- ERROR: Failed to enable course shopping for {sis_id} ({canvas_id}) ({error})"
                        )
                        outFile.write(f"{sis_id}, {canvas_id}, 'err', 'err', 'err'")

                    if update:
                        print(f") Updating course...")

                        try:
                            canvas_course.update(
                                course={"is_public_to_auth_users": True}
                            )
                            status = "public to auth users"
                        except Exception:
                            status = "ERROR"

                        outFile.write(
                            f"{sis_id}, {canvas_id}, {status}, {published}, {notes}"
                        )

                        master = open(MASTER_FILE, "a")
                        master.write(
                            f"{sis_id}, {canvas_id}, {status}, {published}, {notes}"
                        )
                        master.close()

    dataFile.close()
    outFile.close()


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


def course_shopping_main(term, test):
    if test:
        typer.echo("~~This is a TEST~~")
    typer.echo(term)


# load_master()
# print(canvas_id_in_master)

# WHARTON_enable_course_shopping(INFILE, WH_OUTFILE)
# print("WHARTON completed")

# enable_course_shopping(INFILE, OUTFILE)
# print("All completed")

# disable_course_shopping(MASTER_FILE, DISABLE_OUTFILE)
# disable_course_shopping(WH_OUTFILE, WH_DISABLE_OUTFILE)
