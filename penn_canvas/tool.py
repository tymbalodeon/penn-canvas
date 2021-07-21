"""
columns are saved from these reports: canvas_course_id,course_id,short_name,canvas_account_id,term_id,status

"""

from .helpers import get_canvas

terms = ("2020C", "2021A")

TESTING = False

canvas = get_canvas(TESTING)

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
                    if tab.label == "Piazza" and tab.visibility == "public":
                        if canvas_account_id not in schools.keys():
                            account = canvas.get_account(canvas_account_id)
                            schools[canvas_account_id] = account.name

                        school = schools[canvas_account_id]

                        print(f"{course_id}, {t}, {school}")
                        output.write(f"{course_id}\t{t}\t{school}\n")
        except Exception as error:
            print(f"ERROR: {error} {line}")

    tf.close()

output.close()


def tool_main():
    pass
