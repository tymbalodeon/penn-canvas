from datetime import datetime
from html.parser import HTMLParser
from io import StringIO
from json import loads
from os import remove
from pathlib import Path
from re import search
from time import sleep
from zipfile import ZipFile

import requests
from pandas import DataFrame, read_csv
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


def get_students(course):
    echo(") Finding students...")
    students = [
        enrollment
        for enrollment in course.get_enrollments()
        if enrollment.type == "StudentEnrollment"
    ]
    return students, len(students)


def get_quizzes(course):
    echo(") Finding quizzes...")
    quizzes = [quiz for quiz in course.get_quizzes()]
    return quizzes, len(quizzes)


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
                response = requests.get(url, stream=True)
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
    use_timestamp,
):
    user = " ".join(entry.user["display_name"].split())
    user_id = entry.user["id"]
    canvas_user = canvas.get_user(user_id)
    email = canvas_user.email
    message = " ".join(strip_tags(entry.message.replace("\n", " ")).strip().split())
    timestamp = (
        datetime.strptime(entry.created_at, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%m/%d/%Y, %H:%M:%S"
        )
        if use_timestamp
        else ""
    )
    if verbose:
        user_display = color(user, "cyan")
        timestamp_display = color(timestamp, "yellow") if use_timestamp else ""
        email_display = color(email, "yellow") if not use_timestamp else ""
        discussion_display = color(discussion.title.strip(), "magenta")
        if entry_index == 0:
            echo(f"==== DISCUSSION {discussion_index + 1} ====")
        echo(
            f"- [{discussion_index + 1}/{total_discussions}]"
            f" ({entry_index + 1}/{total_entries}) {discussion_display}"
            f" {user_display}"
            f" {timestamp_display if use_timestamp else email_display}"
            f" {message[:40]}..."
        )
    return (
        [user, email, timestamp, message] if use_timestamp else [user, email, message]
    )


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
        response = requests.get(url, stream=True)
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
        course_string = f"course_{course.id}"
        print(course_string)
        announcements = [
            announcement
            for announcement in course.get_discussion_topics(only_announcements=True)
        ]
        for announcement in announcements:
            title = (
                announcement.title.replace(" ", "_").replace("/", "-").replace(":", "-")
            )
            title_path = announcements_path / f"{title}.txt"
            with open(title_path, "w") as announcement_file:
                announcement_file.write(strip_tags(announcement.message))

    def archive_modules(course, course_path):
        modules_path = course_path / "Modules"
        if not modules_path.exists():
            Path.mkdir(modules_path)
        modules = [module for module in course.get_modules()]
        for module in modules:
            module_name = (
                module.name.replace(" ", "_").replace("/", "-").replace(":", "-")
            )
            module_path = modules_path / module_name
            if not module_path.exists():
                Path.mkdir(module_path)
            items = [item for item in module.get_module_items()]
            for item in items:
                body = ""
                try:
                    url = item.url
                except Exception:
                    url = ""
                if url:
                    headers = {
                        "Authorization": (
                            "Bearer"
                            f" {get_config_option('canvas_keys', 'canvas_prod_key')}"
                        )
                    }
                    response = requests.get(url, headers=headers)
                    content = loads(response.content.decode("utf-8"))
                    body = content["body"] if "body" in content else ""
                item_title = (
                    item.title.replace(" ", "_").replace("/", "-").replace(":", "-")
                )
                with open(module_path / f"{item_title}.txt", "w") as item_file:
                    if body:
                        item_file.write(strip_tags(body))
                    elif url:
                        item_file.write(f"[{item.type}]")
                    else:
                        item_file.write("[missing url]")

    def archive_pages(course, course_path):
        pages_path = course_path / "Pages"
        if not pages_path.exists():
            Path.mkdir(pages_path)
        pages = [page for page in course.get_pages()]
        for page in pages:
            title = page.title.replace(" ", "_").replace("/", "-").replace(":", "-")
            page_path = pages_path / f"{title}.txt"
            with open(page_path, "w") as page_file:
                page_file.write(strip_tags.page.show_latest_revision().body)

    def archive_syllabus(course, course_path):
        syllabus_path = course_path / "Syllabus"
        if not syllabus_path.exists():
            Path.mkdir(syllabus_path)
        syllabus = course.syllabus_body
        if syllabus:
            with open(syllabus_path / "syllabus.txt", "w") as syllabus_file:
                syllabus_file.write(strip_tags(syllabus))

    def archive_assignment(canvas, assignment, index=0, total=0):
        assignment_name = (
            assignment.name.strip()
            .replace(" ", "_")
            .replace("/", "-")
            .replace(":", "-")
        )
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

    def archive_discussion(canvas, discussion, verbose=False, index=0, total=0):
        discussion_name = (
            discussion.title.strip()
            .replace(" ", "_")
            .replace("/", "-")
            .replace(":", "-")
        )
        discussion_path = DISCUSSION_DIRECTORY / discussion_name
        if not discussion_path.exists():
            Path.mkdir(discussion_path)
        posts_path = discussion_path / f"{discussion_name}_POSTS.csv"
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
                use_timestamp,
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
        entries = DataFrame(entries, columns=columns)
        entries.to_csv(posts_path, index=False)
        with open(description_path, "w") as description_file:
            description_file.write(description)

    def archive_grade(canvas, student, index=0, total=0, verbose=False):
        grades_path = GRADE_DIRECTORY / "Grades.csv"
        name = canvas.get_user(student.user_id).name
        grade = student.grades["final_grade"]
        score = student.grades["final_score"]
        grades = DataFrame(
            {"Student": [name], "Final Grade": [grade], "Final Score": [score]},
        )
        if grades_path.exists():
            grades = read_csv(grades_path).append(grades).drop_duplicates("Student")
        grades.to_csv(grades_path, index=False)
        if verbose:
            user_display = color(name, "cyan")
            echo(
                f" - ({index + 1}/{total}) {user_display}:"
                f" {color(grade, 'yellow')} ({score})"
            )

    def archive_quizzes(quiz):
        title = (
            quiz.title.replace("-", "")
            .replace(" ", "_")
            .replace("/", "-")
            .replace(":", "-")
        )
        description = strip_tags(quiz.description)
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
        with open(description_path, "w") as description_file:
            description_file.write(description)

    CANVAS = get_canvas(instance)
    course = CANVAS.get_course(course_id, include=["syllabus_body"])
    course_name = course.name.replace("/", "-").replace(":", "-")
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
    if assignments:
        assignments, assignment_total = get_assignments(course)
        echo(") Processing assignments...")
        if verbose:
            for index, assignment in enumerate(assignments):
                archive_assignment(CANVAS, assignment, index, assignment_total)
        else:
            with progressbar(assignments, length=assignment_total) as progress:
                for assignment in progress:
                    archive_assignment(CANVAS, assignment)
    if discussions:
        discussions, discussion_total = get_discussions(course)
        echo(") Processing discussions...")
        if verbose:
            for index, discussion in enumerate(discussions):
                archive_discussion(CANVAS, discussion, True, index, discussion_total)
        else:
            with progressbar(discussions, length=discussion_total) as progress:
                for discussion in progress:
                    archive_discussion(CANVAS, discussion)
    if grades:
        students, student_total = get_students(course)
        echo(") Processing grades...")
        if verbose:
            for index, student in enumerate(students):
                archive_grade(CANVAS, student, index, student_total, verbose)
        else:
            with progressbar(students, length=student_total) as progress:
                for assignment in progress:
                    archive_assignment(CANVAS, assignment)
    if quizzes:
        quizzes, quiz_total = get_quizzes(course)
        echo(") Processing quizzes...")
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
