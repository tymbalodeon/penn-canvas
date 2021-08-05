from pathlib import Path

from typer import progressbar

from .helpers import get_canvas, toggle_progress_bar

COMMAND_DIRECTORY = Path.home() / f"penn-canvas/archive"
RESULTS = COMMAND_DIRECTORY / "results"


def archive_main(course_id, verbose):
    canvas = get_canvas("open")
    course = canvas.get_course(course_id)
    discussions = course.get_discussion_topics()
    report = ""
    total = len(discussions)

    def archive_discussion(discussion, verbose=False, total=0):
        outputfile = discussion.title.replace(" ", "") + ".csv"
        # outFile = open(os.path.join(my_path, "ACP/data", outputfile), "w+")
        entries = discussion.get_topic_entries()

        for entry in entries:
            post = entry.message.replace("\n", "")
            user = entry.user["display_name"]
            created = entry.created_at
            # outFile.write("%s|%s|%s\n" % (user, created, post))

    if verbose:
        for discussion in discussions:
            archive_discussion(discussion, True, total)
    else:
        with progressbar(
            discussions.itertuples(), length=len(discussions.index)
        ) as progress:
            for discussion in progress:
                archive_discussion(discussion)
