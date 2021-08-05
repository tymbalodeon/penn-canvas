from pathlib import Path

from typer import progressbar, echo

from .helpers import (
    TODAY_AS_Y_M_D,
    get_canvas,
    toggle_progress_bar,
    get_start_index,
    make_csv_paths,
    make_skip_message,
)

COMMAND_DIRECTORY = Path.home() / f"penn-canvas/archive"
RESULTS = COMMAND_DIRECTORY / "results"
RESULT_PATH = RESULTS / f"{TODAY_AS_Y_M_D}_archive_result.csv"
HEADERS = ["index", "student", "time created", "post"]


def get_discussions(course_id, instance, start):
    echo(") Finding discussions...")

    canvas = get_canvas(instance)
    course = canvas.get_course(course_id)
    discussions = course.get_discussion_topics()[start:]
    total = len(discussions)

    return discussions, total


def archive_main(course_id, instance, verbose, force):
    def archive_discussion(discussion, verbose=False, total=0):
        outputfile = discussion.title.replace(" ", "") + ".csv"
        # outFile = open(os.path.join(my_path, "ACP/data", outputfile), "w+")
        entries = discussion.get_topic_entries()

        for entry in entries:
            post = entry.message.replace("\n", "")
            user = entry.user["display_name"]
            created = entry.created_at
            # outFile.write("%s|%s|%s\n" % (user, created, post))

    START = get_start_index(force, RESULT_PATH)
    discussions, total = get_discussions(course_id, instance, START)
    make_csv_paths(RESULTS, RESULT_PATH, HEADERS)
    make_skip_message(START, "post")

    echo(") Processing discussions...")

    if verbose:
        for discussion in discussions:
            archive_discussion(discussion, True, total)
    else:
        with progressbar(
            discussions.itertuples(), length=len(discussions.index)
        ) as progress:
            for discussion in progress:
                archive_discussion(discussion)
