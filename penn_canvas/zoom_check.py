"""
baowei@upenn.edu
Jan 28, 2021

This program looks for courses that have enabled Zoom.
It's done by checking a tab with id context_external_tool_231623
The courses are enumerated from a provision report of all courses of 2021A term,
the same report used for course shopping and library reserve
"""

from canvas_shared import get_canvas

canvas = get_canvas(False)

fin = open("data/course_shopping_27_Jan_2021.csv", "r")

fin.readline()

for line in fin:
    canvas_id, sis_id, short_name, account_id, status = line.replace("\n", "").split(
        ","
    )

    canvas_course = canvas.get_course(canvas_id)

    tools = canvas_course.get_external_tools()

    tabs = canvas_course.get_tabs()
    for t in tabs:
        if t.id == "context_external_tool_231623" and t.visibility == "public":
            print("%s,%s,%s" % (canvas_id, short_name, status))

fin.close()
