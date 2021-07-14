import os
import sys

import typer

from .helpers import get_canvas, get_command_paths

REPORTS, RESULTS = get_command_paths("group_enrollments")
RESULT_PATH = RESULTS / "result.csv"
HEADERS = ["course id, group set, group, pennkey, status"]


def find_group(name, groups):
    found = None
    for group in groups:
        if group.name == name:
            found = group
    return found


def create_group_enrollments(
    inputfile="groups.csv", outputfile="NSO_group_enrollments.csv", test=False
):
    canvas = get_canvas(test)
    my_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    file_path = os.path.join(my_path, "ACP/data", inputfile)
    dataFile = open(file_path, "r")
    dataFile.readline()
    outFile = open(os.path.join(my_path, "ACP/data", outputfile), "w+")
    outFile.write("canvas_course_id, group_set, group, pennkey, status\n")

    for line in dataFile:
        course_id, groupset_name, group_name, pennkey = line.replace("\n", "").split(
            ","
        )

        canvas_site = canvas.get_course(course_id)

        try:
            group_set = find_group(groupset_name, canvas_site.get_group_categories())

            if group_set is None:
                raise TypeError

        except Exception:
            print("creating group set: ", groupset_name)
            group_set = canvas_site.create_group_category(groupset_name)

        try:
            group = find_group(group_name, group_set.get_groups())
            if group is None:
                raise TypeError

        except Exception:
            print("creating group: ", group_name)
            group = group_set.create_group(name=group_name)

        try:
            user = canvas.get_user(pennkey, "sis_login_id")
            group.create_membership(user)

            message = (
                f"{course_id}, {groupset_name}, {group_name}, {pennkey}, 'accepted'\n"
            )
            print(message)
            outFile.write(message)
        except Exception:
            message = (
                f"{course_id}, {groupset_name}, {group_name}, {pennkey}, 'failed'\n"
            )
            typer.echo(message)
            outFile.write(message)


def group_enrollments_main():
    typer.echo("HELLO")
