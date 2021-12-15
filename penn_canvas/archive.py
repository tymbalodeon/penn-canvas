from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from json import loads
from mimetypes import guess_extension
from os import remove
from pathlib import Path
from re import search
from time import sleep
from zipfile import ZipFile

from magic import from_file
from pandas import DataFrame
from requests import get
from typer import echo, progressbar

from .config import get_config_option
from .helpers import get_canvas, get_command_paths
from .style import color

COMMAND = "Archive"
RESULTS = get_command_paths(COMMAND, no_input=True)[0]


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()


def strip_tags(html):
    stripper = HTMLStripper()
    stripper.feed(html)
    return stripper.get_data()


def get_assignments(course):
    echo(") Finding assignments...")
    assignments = [assignment for assignment in course.get_assignments()]
    return assignments, len(assignments)


def get_discussions(course):
    echo(") Finding discussions...")
    discussions = [discussion for discussion in course.get_discussion_topics()]
    return discussions, len(discussions)


def get_enrollments(course):
    echo(") Finding students...")
    enrollments = [
        enrollment
        for enrollment in course.get_enrollments()
        if enrollment.type == "StudentEnrollment"
    ]
    return enrollments


def get_quizzes(course):
    echo(") Finding quizzes...")
    quizzes = [quiz for quiz in course.get_quizzes()]
    return quizzes, len(quizzes)


def format_name(name):
    return name.strip().replace("/", "-").replace(":", "-")


def get_submission_score(submission):
    return round(float(submission.score), 2) if submission.score else submission.score


def process_submission(
    submission,
    verbose,
    assignment_index,
    total_assignments,
    submission_index,
    total_submissions,
    assignment,
    assignment_path,
    comments_path,
    canvas,
):
    user = canvas.get_user(submission.user_id).name
    try:
        grader = canvas.get_user(submission.grader_id).name
    except Exception:
        grader = None
    try:
        grade = round(float(submission.grade), 2)
    except Exception:
        grade = submission.grade
    try:
        score = round(submission.score, 2)
    except Exception:
        score = submission.score
    submissions_path = assignment_path / "Submission Files"
    try:
        body = strip_tags(submission.body.replace("\n", " ")).strip()
        with open(
            submissions_path / f"{assignment}_SUBMISSION ({user}).txt", "w"
        ) as submissions_file:
            submissions_file.write(body)
    except Exception:
        body = ""
    if not submissions_path.exists():
        Path.mkdir(submissions_path)
    try:
        attachments = [
            (attachment["url"], attachment["filename"])
            for attachment in submission.attachments
        ]
        for url, filename in attachments:
            name, extension = filename.split(".")
            with open(
                submissions_path / f"{name} ({user}).{extension}", "wb"
            ) as stream:
                response = get(url, stream=True)
                for chunk in response.iter_content(chunk_size=128):
                    stream.write(chunk)
    except Exception:
        attachments = []
    comments = [
        [submission["author_name"], submission["comment"]]
        for submission in submission.submission_comments
    ]
    comments = DataFrame(comments, columns=["Name", "Comment"])
    submission_comments_path = comments_path / f"{assignment}_COMMENTS ({user}).csv"
    comments.to_csv(submission_comments_path, index=False)
    if verbose:
        user_display = color(user, "cyan")
        if submission_index == 0:
            color(
                f"==== ASSIGNMENT {assignment_index + 1}/{total_assignments}:"
                f" {assignment} ====",
                "magenta",
                True,
            )
        echo(
            f" - ({submission_index + 1}/{total_submissions})"
            f" {user_display} {color(grade, 'yellow')}"
        )
    return [
        user,
        submission.submission_type.replace("_", " ")
        if submission.submission_type
        else submission.submission_type,
        grade,
        score,
        grader,
    ]


def process_entry(
    entry,
    verbose,
    discussion_index,
    total_discussions,
    entry_index,
    total_entries,
    discussion,
    canvas,
    csv_style,
):
    user = " ".join(entry.user["display_name"].split())
    user_id = entry.user["id"]
    canvas_user = canvas.get_user(user_id)
    email = canvas_user.email if csv_style else ""
    message = " ".join(strip_tags(entry.message.replace("\n", " ")).strip().split())
    timestamp = (
        ""
        if csv_style
        else datetime.strptime(entry.created_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%m/%d/%Y, %H:%M:%S"
        )
    )
    if verbose:
        user_display = color(user, "cyan")
        timestamp_display = color(timestamp, "yellow") if csv_style else ""
        email_display = color(email, "yellow") if not csv_style else ""
        discussion_display = color(discussion.title.strip(), "magenta")
        if entry_index == 0:
            echo(f"==== DISCUSSION {discussion_index + 1} ====")
        echo(
            f"- [{discussion_index + 1}/{total_discussions}]"
            f" ({entry_index + 1}/{total_entries}) {discussion_display}"
            f" {user_display}"
            f" {timestamp_display if csv_style else email_display}"
            f" {message[:40]}..."
        )
    return [user, email, message] if csv_style else (user, timestamp, message)


def archive_main(
    course_id,
    instance,
    verbose,
    use_timestamp,
    content,
    announcements,
    modules,
    pages,
    syllabus,
    assignments,
    discussions,
    grades,
    quizzes,
):
    if (
        content
        == announcements
        == modules
        == pages
        == syllabus
        == assignments
        == discussions
        == grades
        == quizzes
        is False
    ):
        content = (
            announcements
        ) = (
            modules
        ) = pages = syllabus = assignments = discussions = grades = quizzes = True

    def archive_content(course, course_path, canvas, verbose):
        export = course.export_content(export_type="zip", skip_notifications=True)
        regex_search = search(r"\d*$", export.progress_url)
        progress_id = regex_search.group() if regex_search else None
        progress = canvas.get_progress(progress_id)
        while progress.workflow_state != "completed":
            if verbose:
                echo(f"- {course.name} export {progress.workflow_state}...")
            sleep(8)
            progress = canvas.get_progress(progress_id)
        url = course.get_content_export(export).attachment["url"]
        response = get(url, stream=True)
        zip_path = course_path / "content.zip"
        content_path = course_path / "Content"
        if not content_path.exists():
            Path.mkdir(content_path)
        with open(course_path / "content.zip", "wb") as stream:
            for chunk in response.iter_content(chunk_size=128):
                stream.write(chunk)
        with ZipFile(zip_path) as unzipper:
            unzipper.extractall(content_path)
        remove(zip_path)

    def archive_announcements(course, course_path):
        announcements_path = course_path / "Announcements"
        if not announcements_path.exists():
            Path.mkdir(announcements_path)
        announcements = [
            announcement
            for announcement in course.get_discussion_topics(only_announcements=True)
        ]
        for announcement in announcements:
            title = format_name(announcement.title)
            title_path = announcements_path / f"{title}.txt"
            with open(title_path, "w") as announcement_file:
                announcement_file.write(strip_tags(announcement.message))

    def archive_modules(course, course_path):
        modules_path = course_path / "Modules"
        if not modules_path.exists():
            Path.mkdir(modules_path)
        modules = [module for module in course.get_modules()]
        for module in modules:
            module_name = format_name(module.name)
            module_path = modules_path / module_name
            if not module_path.exists():
                Path.mkdir(module_path)
            items = [item for item in module.get_module_items()]
            for item in items:
                content = None
                extension = ".txt"
                body = ""
                try:
                    url = item.url
                except Exception:
                    try:
                        url = item.html_url
                    except Exception:
                        url = ""
                if url:
                    headers = {
                        "Authorization": (
                            "Bearer"
                            f" {get_config_option('canvas_keys', 'canvas_prod_key')}"
                        )
                    }
                    response = get(url, headers=headers)
                    try:
                        content = loads(response.content.decode("utf-8"))
                        if item.type == "File":
                            file_url = content["url"] if "url" in content else ""
                            if file_url:
                                try:
                                    name, extension = item.filename.split(".")
                                except Exception:
                                    try:
                                        name, extension = item.title.split(".")
                                    except Exception:
                                        name = item.title
                                        extension = ""
                                name = format_name(name)
                                filename = (
                                    f"{name}.{extension.lower()}"
                                    if extension
                                    else f"{name}"
                                )
                                file_path = module_path / filename
                                with open(file_path, "wb") as stream:
                                    response = get(
                                        file_url, headers=headers, stream=True
                                    )
                                    for chunk in response.iter_content(chunk_size=128):
                                        stream.write(chunk)
                                if not extension:
                                    mime_type = from_file(str(file_path), mime=True)
                                    file_path.rename(
                                        f"{file_path}{guess_extension(mime_type)}"
                                    )
                            continue
                        body = content["body"] if "body" in content else ""
                    except Exception:
                        body = (
                            f"[ExternalUrl]: {item.external_url}"
                            if item.type == "ExternalUrl"
                            else ""
                        )
                item_title = format_name(item.title)
                with open(module_path / f"{item_title}{extension}", "w") as item_file:
                    if body:
                        file_content = strip_tags(body)
                    elif url:
                        file_content = f"[{item.type}]"
                    else:
                        file_content = "[missing url]"
                    item_file.write(file_content)

    def archive_pages(course, course_path):
        pages_path = course_path / "Pages"
        if not pages_path.exists():
            Path.mkdir(pages_path)
        pages = [page for page in course.get_pages()]
        for page in pages:
            title = format_name(page.title)
            page_path = pages_path / f"{title}.txt"
            with open(page_path, "w") as page_file:
                page_file.write(strip_tags(page.show_latest_revision().body))

    def archive_syllabus(course, course_path):
        syllabus_path = course_path / "Syllabus"
        if not syllabus_path.exists():
            Path.mkdir(syllabus_path)
        syllabus = course.syllabus_body
        if syllabus:
            with open(syllabus_path / "syllabus.txt", "w") as syllabus_file:
                syllabus_file.write(strip_tags(syllabus))

    def archive_assignment(canvas, assignment, index=0, total=0, verbose=False):
        assignment_name = format_name(assignment.name)
        assignment_path = ASSIGNMENT_DIRECTORY / assignment_name
        if not assignment_path.exists():
            Path.mkdir(assignment_path)
        description_path = assignment_path / f"{assignment_name}_DESCRIPTION.txt"
        submissions_path = assignment_path / f"{assignment_name}_GRADES.csv"
        comments_path = assignment_path / "Submission Comments"
        if not comments_path.exists():
            Path.mkdir(comments_path)
        submissions = [
            submission
            for submission in assignment.get_submissions(include="submission_comments")
        ]
        submissions = [
            process_submission(
                submission,
                verbose,
                index,
                total,
                submission_index,
                len(submissions),
                assignment_name,
                assignment_path,
                comments_path,
                canvas,
            )
            for submission_index, submission in enumerate(submissions)
        ]
        try:
            description = " ".join(
                strip_tags(assignment.description.replace("\n", " ")).strip().split()
            )
        except Exception:
            description = ""
        columns = ["User", "Submission type", "Grade", "Score", "Grader"]
        submissions = DataFrame(submissions, columns=columns)
        submissions.to_csv(submissions_path, index=False)
        with open(description_path, "w") as assignment_file:
            assignment_file.write(description)

    def archive_discussion(
        canvas, discussion, csv_style=False, index=0, total=0, verbose=False
    ):
        discussion_name = format_name(discussion.title)
        discussion_path = DISCUSSION_DIRECTORY / discussion_name
        if not discussion_path.exists():
            Path.mkdir(discussion_path)
        description_path = discussion_path / f"{discussion_name}_DESCRIPTION.txt"
        entries = [entry for entry in discussion.get_topic_entries()]
        if verbose and not entries:
            echo(f"==== DISCUSSION {index + 1} ====")
            echo("- NO ENTRIES")
        entries = [
            process_entry(
                entry,
                verbose,
                index,
                total,
                entry_index,
                len(entries),
                discussion,
                canvas,
                csv_style,
            )
            for entry_index, entry in enumerate(entries)
        ]
        try:
            description = " ".join(
                strip_tags(discussion.message.replace("\n", " ")).strip().split()
            )
        except Exception:
            description = ""
        columns = ["User", "Email", "Timestamp", "Post"]
        if not use_timestamp:
            columns.remove("Timestamp")
        if csv_style:
            entries = DataFrame(entries, columns=columns)
            posts_path = discussion_path / f"{discussion_name}_POSTS.csv"
            entries.to_csv(posts_path, index=False)
        else:
            posts_path = discussion_path / f"{discussion_name}_POSTS.txt"
            with open(posts_path, "w") as posts_file:
                for user, timestamp, message in entries:
                    posts_file.write(f"\n{user}\n{timestamp}\n\n{message}\n")
        with open(description_path, "w") as description_file:
            description_file.write(description)

    def archive_grade(canvas, enrollment, submissions):
        def get_score_from_submissions(submissions, user_id):
            return next(item[1] for item in submissions if item[0] == user_id)

        user_id = enrollment.user_id
        user = enrollment.user
        name = user["sortable_name"]
        sis_user_id = user["sis_user_id"]
        login_id = user["login_id"]
        section_id = canvas.get_section(enrollment.course_section_id).name
        student_data = [name, user_id, sis_user_id, login_id, section_id]
        submission_scores = [
            get_score_from_submissions(submission[1], user_id)
            for submission in submissions
        ]
        current_score = enrollment.grades["current_score"]
        unposted_current_score = enrollment.grades["unposted_current_score"]
        final_score = enrollment.grades["final_score"]
        unposted_final_score = enrollment.grades["unposted_final_score"]
        current_grade = enrollment.grades["current_grade"]
        unposted_current_grade = enrollment.grades["unposted_current_grade"]
        final_grade = enrollment.grades["final_grade"]
        unposted_final_grade = enrollment.grades["unposted_final_grade"]
        total_scores = [
            current_score,
            unposted_current_score,
            final_score,
            unposted_final_score,
            current_grade,
            unposted_current_grade,
            final_grade,
            unposted_final_grade,
        ]
        return student_data + submission_scores + total_scores

    def archive_quizzes(quiz):
        title = format_name(quiz.title)
        description = (
            strip_tags(quiz.description) if quiz.description else quiz.description
        )
        questions = [
            [
                strip_tags(question.question_text),
                ", ".join([answer["text"] for answer in question.answers]),
            ]
            for question in quiz.get_questions()
        ]
        submissions = [submission for submission in quiz.get_submissions()]
        quiz_path = QUIZ_DIRECTORY / title
        description_path = quiz_path / f"{title}_DESCRIPTION.txt"
        questions_path = quiz_path / f"{title}_QUESTIONS.csv"
        scores_path = quiz_path / f"{title}_SCORES.csv"
        if not quiz_path.exists():
            Path.mkdir(quiz_path)
        user_scores = [
            [CANVAS.get_user(submission.user_id).name, round(submission.score, 2)]
            for submission in submissions
        ]
        user_scores = DataFrame(user_scores, columns=["Student", "Score"])
        questions = DataFrame(questions, columns=["Question", "Answers"])
        user_scores.to_csv(scores_path, index=False)
        questions.to_csv(questions_path, index=False)
        if description:
            with open(description_path, "w") as description_file:
                description_file.write(description)

    CANVAS = get_canvas(instance)
    course = CANVAS.get_course(course_id, include=["syllabus_body"])
    course_name = format_name(course.name)
    discussion_total = 0
    quiz_total = 0
    COURSE = RESULTS / course_name
    ASSIGNMENT_DIRECTORY = COURSE / "Assignments"
    DISCUSSION_DIRECTORY = COURSE / "Discussions"
    GRADE_DIRECTORY = COURSE / "Grades"
    QUIZ_DIRECTORY = COURSE / "Quizzes"
    PATHS = [
        COURSE,
        ASSIGNMENT_DIRECTORY,
        DISCUSSION_DIRECTORY,
        GRADE_DIRECTORY,
        QUIZ_DIRECTORY,
    ]
    for path in PATHS:
        if not path.exists():
            Path.mkdir(path)
    if content:
        echo(") Exporting content...")
        archive_content(course, COURSE, CANVAS, verbose)
    if announcements:
        echo(") Exporting announcements...")
        archive_announcements(course, COURSE)
    if modules:
        echo(") Exporting modules...")
        archive_modules(course, COURSE)
    if pages:
        echo(") Exporting pages...")
        archive_pages(course, COURSE)
    if syllabus:
        echo(") Exporting syllabus...")
        archive_syllabus(course, COURSE)
    assignment_objects = []
    if assignments:
        echo(") Processing assignments...")
        assignment_objects, assignment_total = get_assignments(course)
        if verbose:
            for index, assignment in enumerate(assignment_objects):
                archive_assignment(CANVAS, assignment, index, assignment_total, verbose)
        else:
            with progressbar(assignment_objects, length=assignment_total) as progress:
                for assignment in progress:
                    archive_assignment(CANVAS, assignment)
    if discussions:
        echo(") Processing discussions...")
        discussions, discussion_total = get_discussions(course)
        if verbose:
            for index, discussion in enumerate(discussions):
                archive_discussion(
                    CANVAS,
                    discussion,
                    index=index,
                    total=discussion_total,
                    verbose=verbose,
                )
        else:
            with progressbar(discussions, length=discussion_total) as progress:
                for discussion in progress:
                    archive_discussion(CANVAS, discussion)
    if grades:

        def get_manual_posting(assignment):
            return "Manual Posting" if assignment.post_manually else ""

        echo(") Processing grades...")
        enrollments = get_enrollments(course)
        if not assignments:
            assignment_objects, assignment_total = get_assignments(course)
        assignment_objects = [
            assignment for assignment in assignment_objects if assignment.published
        ]
        assignment_posted = [""] * 5 + [
            get_manual_posting(assignment) for assignment in assignment_objects
        ]
        assignment_points = (
            ["    Points Possible"]
            + [""] * 4
            + [assignment.points_possible for assignment in assignment_objects]
            + (["(read only)"] * 8)
        )
        submissions = [
            (
                format_name(assignment.name),
                [
                    (submission.user_id, get_submission_score(submission))
                    for submission in assignment.get_submissions()
                ],
            )
            for assignment in assignment_objects
        ]
        assignment_names = [submission[0] for submission in submissions]
        columns = (
            [
                "Student",
                "ID",
                "SIS User ID",
                "SIS Login ID",
                "Section",
            ]
            + assignment_names
            + [
                "Current Score",
                "Unposted Current Score",
                "Final Score",
                "Unposted Final Score",
                "Current Grade",
                "Unposted Current Grade",
                "Final Grade",
                "Unposted Final Grade",
            ]
        )
        grades_path = GRADE_DIRECTORY / "Grades.csv"
        rows = (
            [assignment_posted]
            + [assignment_points]
            + [
                archive_grade(CANVAS, enrollment, submissions)
                for enrollment in enrollments
            ]
        )
        grade_book = DataFrame(rows, columns=columns)
        grade_book.to_csv(grades_path, index=False)
    if quizzes:
        echo(") Processing quizzes...")
        quizzes, quiz_total = get_quizzes(course)
        if verbose:
            for index, quiz in enumerate(quizzes):
                archive_quizzes(quiz)
        else:
            with progressbar(quizzes, length=quiz_total) as progress:
                for quiz in progress:
                    archive_quizzes(quiz)
    color("SUMMARY", "yellow", True)
    echo(
        f"- Archived {color(discussion_total, 'magenta')} DISCUSSIONS for"
        f" {color(course.name, 'blue')}."
    )
    if quizzes:
        echo(
            f"- Archived {color(quiz_total, 'magenta')} QUIZZES for"
            f" {color(course.name, 'blue')}."
        )
    color("FINISHED", "yellow", True)
