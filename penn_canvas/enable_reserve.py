import datetime
from canvas_shared import *

# Use this function add_reserves to enable the reserves at Penn Library button on courses
# Annenberg 99243
# BGS 128877
# Design 99244
# Nursing 99239
# PSOM 99242
# SAS 99237
# SEAS 99238
# SP2 99240

TESTING = False  # True to run on test site, False to run on the production
TERM = "2021A"

t = datetime.datetime.now().strftime("%d_%b_%Y")

MASTER_FILE = "data/Reserves_Master_" + TERM + ".csv"

master_list_already_added = []


# load the master file for all courses already added
def load_master():
    master = open(MASTER_FILE, "r")
    master.readline()  # skip the first line

    for line in master:

        canvas_course_id, course_id, account, reserves = line.strip().split(",")
        if "added" in reserves:
            master_list_already_added.append(canvas_course_id.strip())

    master.close()


def add_to_master(line):
    master = open(MASTER_FILE, "a")
    master.write(line + "\n")
    master.close()


# canvas_course_id, sis_id, canvas_account_id = line.replace("\n","").split(",")
def add_reserves(
    inputfile="reserves_" + t + ".csv", outputfile="RESULT_Reserves_" + t + ".csv"
):
    # this script will enable reserves given an input file that contains only one column ( the sis id)
    # if reserves are already enabled it wil note that and not update the site.

    RESERVES = "context_external_tool_139969"
    SUB_ACCOUNTS = [99237, 128877, 99244, 99238, 99239, 99240, 99242, 99243]

    canvas = get_canvas(TESTING)

    dataFile = open("data/" + inputfile, "r")
    dataFile.readline()  # THIS SKIPS THE FIRST LINE

    outFile = open("data/" + outputfile, "w+")
    outFile.write(
        "%s,%s,%s,%s\n" % ("canvas_course_id", "course_id", "account", "Reserves")
    )

    ## build a list of sub account's sub accounts
    SUB_SUB_ACCOUNTS = []
    for sub in SUB_ACCOUNTS:
        SUB_SUB_ACCOUNTS += find_accounts_subaccounts(canvas, sub)

    print(SUB_SUB_ACCOUNTS)
    # return SUB_SUB_ACCOUNTS

    for line in dataFile:
        # canvas_course_id	course_id	canvas_account_id
        canvas_course_id, sis_id, canvas_account_id = line.replace("\n", "").split(",")

        outFile.write("%s, %s, %s" % (canvas_course_id, sis_id, canvas_account_id))

        if not canvas_account_id.isnumeric():
            print("\t Invalid canvas_account_id: %s", canvas_account_id)
            outFile.write(",%s\n" % "invalid canvas_account_id")
        elif canvas_course_id in master_list_already_added:
            print("\t Already added in master file")
            outFile.write(",%s\n" % "already added in master")
        else:
            if int(canvas_account_id) in SUB_SUB_ACCOUNTS:
                try:
                    canvas_course = canvas.get_course(canvas_course_id)
                    print("\t found course ", canvas_course)
                except:
                    print("\t didn't find course %s" % canvas_course_id)
                    canvas_course = None
            else:
                print("course %s not in opt in school" % canvas_account_id)
                canvas_course = False

            if canvas_course:
                print("canvas course: %s" % canvas_course.id)
                tabs = canvas_course.get_tabs()
                for tab in tabs:
                    # CONFIGURING RESERVES
                    if tab.id == RESERVES:
                        print("\tfound Reserves")
                        # outFile.write(",%s\n" % 'already added')
                        try:
                            if tab.visibility != "public":
                                tab.update(hidden=False, position=3)
                                print("\t enabled reserves")
                                outFile.write(",%s\n" % "added")

                                # add this line to master file
                                add_to_master(line.strip() + ",added to master")

                            else:
                                print("\t already enabled reserves ")
                                outFile.write(",%s\n" % "already added")
                        except:
                            print("\tfailed reserves %s" % canvas_course_id)
                            outFile.write(",%s\n" % "failed to add")
                    else:
                        # skip this tab
                        pass
                # outFile.write("\n")
            elif canvas_course is None:  # no site
                outFile.write(",%s\n" % "couldn't find")
            elif not canvas_course:  # not in program
                outFile.write(",%s\n" % "not in program")
            else:
                print("HEY YOU SHOULDNT GET TO THIS CASE", canvas_course_id)

    dataFile.close()
    outFile.close()


# add_reserves(inputfile='testing_courses.csv')
def quick_add_reserves(canvas_id):
    canvas = get_canvas(TESTING)
    RESERVES = "context_external_tool_139969"
    try:
        canvas_course = canvas.get_course(canvas_id)
    except:
        return "couldnt find course"

    tabs = canvas_course.get_tabs()
    for tab in tabs:
        # CONFIGURING RESERVES
        if tab.id == RESERVES:
            print("\tfound Reserves")
            try:
                if tab.visibility != "public":
                    tab.update(hidden=False, position=3)
                    print("\t enabled reserves")
                else:
                    print("\t already enabled reserves ")
            except:
                print("\tfailed reserves %s" % canvas_id)
        else:
            # skip this tab
            pass


load_master()
print(master_list_already_added)
add_reserves()
