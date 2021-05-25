"""
Generate a report for terms 2020C, 2021A of active courses with "Piazza" enabled

The source files are provisioning reports of the specific terms. Only these
columns are saved from these reports: canvas_course_id,course_id,short_name,canvas_account_id,term_id,status

Output file is data/piazza_report.csv. Because some school names have comma, in this file tab instead of
comma is used as separator

March 10, 2021
baowei@upenn.edu

"""

from canvas_shared import *

terms = ("2020C", "2021A")

# this is the Id of the Piazza tab
Piazza = "context_external_tool_225770"

TESTING = False

canvas = get_canvas(TESTING)

# use this dictionary for the account id/name lookup
schools = {}

output = open("data/piazza_report.csv", "a")
output.write("Term\tCourse\tSchool\n")

for t in terms:
    csv = "data/courses_" + t + ".csv"
    tf = open(csv, "r")
    tf.readline()

    for line in tf:

        try:
            (
                canvas_course_id,
                course_id,
                short_name,
                canvas_account_id,
                term_id,
                status,
            ) = line.strip().split(",")

            if course_id != "" and status == "active":
                course = canvas.get_course(canvas_course_id)
                tabs = course.get_tabs()

                for tab in tabs:
                    # CONFIGURING RESERVES

                    if tab.label == "Piazza" and tab.visibility == "public":
                        # tab.id == Piazza

                        if canvas_account_id not in schools.keys():
                            account = canvas.get_account(canvas_account_id)
                            schools[canvas_account_id] = account.name

                        school = schools[canvas_account_id]

                        print(course_id + "," + t + "," + school)
                        output.write(course_id + "\t" + t + "\t" + school + "\n")

        except Exception as ex:
            print("Error:" + str(ex) + " (" + line + ")")

    tf.close()

output.close()
