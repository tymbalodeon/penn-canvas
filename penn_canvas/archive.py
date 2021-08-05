from pathlib import Path

from .helpers import get_canvas

COMMAND_DIRECTORY = Path.home() / f"penn-canvas/archive"
RESULTS = COMMAND_DIRECTORY / "results"


def archive_main(course_id, test, verbose):
    canvas = get_canvas(test)
    course = canvas.get_course(course_id)
    discussions = course.get_discussion_topics()

    for discussion in discussions:
        outputfile = discussion.title.replace(" ", "") + ".csv"
        outFile = open(os.path.join(my_path, "ACP/data", outputfile), "w+")
        entries = discussion.get_topic_entries()

        for entry in entries:
            post = entry.message.replace("\n", "")
            user = entry.user["display_name"]
            created = entry.created_at
            outFile.write("%s|%s|%s\n" % (user, created, post))
