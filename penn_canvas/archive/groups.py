from pandas import DataFrame
from requests import get
from typer import echo

from penn_canvas.api import get_user
from penn_canvas.helpers import create_directory
from penn_canvas.style import color, print_item

from .helpers import format_name


def archive_groups(course, course_directory, instance, verbose):
    echo(") Exporting groups...")
    categories = list(course.get_group_categories())
    GROUP_DIRECTORY = create_directory(course_directory / "Groups")
    category_total = len(categories)
    for category_index, category in enumerate(categories):
        groups = list(category.get_groups())
        groups_directory = create_directory(GROUP_DIRECTORY / category.name)
        group_total = len(groups)
        if verbose:
            print_item(category_index, category_total, f"{color(category)}")
        for group_index, group in enumerate(groups):
            group_directory = create_directory(groups_directory / group.name)
            memberships = [
                get_user(membership.user_id, instance=instance)
                for membership in group.get_memberships()
            ]
            memberships = [[user.id, user.name] for user in memberships]
            memberships = DataFrame(memberships, columns=["Canvas User ID", "Name"])
            memberships_path = group_directory / f"{format_name(group.name)}_users.csv"
            memberships.to_csv(memberships_path, index=False)
            files = list(group.get_files())
            if verbose:
                print_item(group_index, group_total, f"{color(group)}")
            file_total = len(files)
            for file_index, group_file in enumerate(files):
                display_name = group_file.display_name
                try:
                    name, extension = display_name.split(".")
                except Exception:
                    name = group_file.filename
                    extension = "txt"
                with open(
                    group_directory / f"{name}.{extension}",
                    "wb",
                ) as stream:
                    response = get(group_file.url, stream=True)
                    for chunk in response.iter_content(chunk_size=128):
                        stream.write(chunk)
                if verbose:
                    print_item(file_index, file_total, f"{color(display_name)}")
