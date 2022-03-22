from html.parser import HTMLParser
from io import StringIO
from json import loads
from mimetypes import guess_extension
from os import remove
from pathlib import Path
from re import search
from time import sleep
from typing import Optional
from zipfile import ZipFile

from canvasapi.assignment import Assignment
from canvasapi.course import Course
from canvasapi.discussion_topic import DiscussionEntry, DiscussionTopic
from canvasapi.enrollment import Enrollment
from canvasapi.quiz import Quiz
from canvasapi.rubric import Rubric
from canvasapi.submission import Submission
from canvasapi.user import User
from magic import from_file
from pandas import DataFrame, read_pickle
from requests import get
from typer import echo, progressbar

from .api import (
    Instance,
    collect,
    get_canvas,
    get_course,
    get_section,
    get_user,
    validate_instance_name,
)
from .config import get_config_option
from .helpers import BASE_PATH, create_directory, format_timestamp, switch_logger_file
from .style import color, print_item

COMMAND_PATH = create_directory(BASE_PATH / "Archive")
RESULTS = create_directory(COMMAND_PATH / "Results")
LOGS = create_directory(COMMAND_PATH / "Logs")
ANNOUNCEMENTS_PICKLE_FILE = "announcements.pkl"


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


def should_run_option(option: Optional[bool], archive_all: bool) -> bool:
    return option if isinstance(option, bool) else archive_all


def format_display_text(text: str, limit=50) -> str:
    truncated = len(text) > limit
    text = text.replace("\n", " ").replace("\t", " ")[:limit]
    if truncated:
        final_character = text[-1]
        while final_character == " " or final_character == ".":
            text = text[:-1]
            final_character = text[-1]
        text = f"{text}..."
    return text


def get_assignments(course: Course) -> tuple[list[Assignment], int]:
    echo(") Finding assignments...")
    assignments = collect(course.get_assignments())
    return assignments, len(assignments)


def get_discussions(course: Course) -> tuple[list[DiscussionTopic], int]:
    echo(") Finding discussions...")
    discussions = collect(course.get_discussion_topics())
    return discussions, len(discussions)


def get_enrollments(course: Course) -> list[Enrollment]:
    echo(") Finding students...")
    enrollments = [
        enrollment
        for enrollment in course.get_enrollments()
        if enrollment.type == "StudentEnrollment"
    ]
    return enrollments


def get_quizzes(course: Course) -> tuple[list[Quiz], int]:
    echo(") Finding quizzes...")
    quizzes = collect(course.get_quizzes())
    return quizzes, len(quizzes)


def get_rubrics(course: Course) -> tuple[list[Rubric], int]:
    echo(") Finding rubrics...")
    rubrics = collect(course.get_rubrics())
    return rubrics, len(rubrics)


def format_name(name: str) -> str:
    return name.strip().replace("/", "-").replace(":", "-")


def get_submission_score(submission: Submission):
    return round(float(submission.score), 2) if submission.score else submission.score


def process_submission(
    submission: Submission,
    instance: Instance,
    verbose: bool,
    assignment_index: int,
    total_assignments: int,
    submission_index: int,
    total_submissions: int,
    assignment: str,
    assignment_path: Path,
    comments_path: Path,
) -> list[User | str | int]:
    user = get_user(submission.user_id, instance=instance).name
    try:
        grader = get_user(submission.grader_id, instance=instance).name
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
    submissions_path = create_directory(assignment_path / "Submission Files")
    try:
        body = strip_tags(submission.body.replace("\n", " ")).strip()
        with open(
            submissions_path / f"{assignment}_SUBMISSION ({user}).txt", "w"
        ) as submissions_file:
            submissions_file.write(body)
    except Exception:
        body = ""
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

    def process_comments(submission: dict) -> str:
        author = submission["author_name"]
        created_at = format_timestamp(submission["created_at"])
        edited_at = (
            format_timestamp(submission["edited_at"]) if submission["edited_at"] else ""
        )
        comment = submission["comment"]
        media_comment = (
            submission["media_comment"]["url"] if "media_comment" in submission else ""
        )
        return (
            f"{author}\nCreated: {created_at}\nEdited:"
            f" {edited_at}\n\n{comment}{media_comment}"
        )

    comments = [
        process_comments(submission) for submission in submission.submission_comments
    ]
    comments_body = "\n\n".join(comments)
    submission_comments_path = comments_path / f"{assignment}_COMMENTS ({user}).txt"
    with open(submission_comments_path, "w") as submission_comments_file:
        submission_comments_file.write(comments_body)
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
    entry: DiscussionEntry,
    instance: Instance,
    verbose: bool,
    discussion_index: int,
    total_discussions: int,
    entry_index: int,
    total_entries: int,
    discussion: DiscussionTopic,
    csv_style: bool,
) -> list | tuple:
    user = " ".join(entry.user["display_name"].split())
    user_id = entry.user["id"]
    canvas_user = get_user(user_id, instance=instance)
    email = canvas_user.email if csv_style else ""
    message = " ".join(strip_tags(entry.message.replace("\n", " ")).strip().split())
    timestamp = "" if csv_style else format_timestamp(entry.created_at)
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


def archive_content(
    course: Course,
    course_directory: Path,
    instance: Instance,
    verbose: bool,
    unzip=False,
):
    echo(") Exporting content...")
    for export_type in ["zip", "common_cartridge"]:
        echo(f') Starting "{export_type}" export...')
        export = course.export_content(export_type=export_type, skip_notifications=True)
        regex_search = search(r"\d*$", export.progress_url)
        progress_id = regex_search.group() if regex_search else None
        canvas = get_canvas(instance)
        progress = canvas.get_progress(progress_id)
        while progress.workflow_state != "completed":
            if verbose:
                echo(f"- {course.name} export {progress.workflow_state}...")
            sleep(5)
            progress = canvas.get_progress(progress_id)
        url = course.get_content_export(export).attachment["url"]
        response = get(url, stream=True)
        file_name = f"{export_type}_content.zip"
        content_path = create_directory(course_directory / "Content")
        export_path = create_directory(
            content_path / export_type.replace("_", " ").title()
        )
        file_path = export_path / file_name
        with open(file_path, "wb") as stream:
            for chunk in response.iter_content(chunk_size=128):
                stream.write(chunk)
        if unzip:
            with ZipFile(file_path) as unzipper:
                unzipper.extractall(export_path)
            remove(file_path)


def process_announcement(announcement: DiscussionTopic) -> list[str]:
    title = format_name(announcement.title)
    message = strip_tags(announcement.message)
    return [title, message]


def display_announcement(index: int, total: int, title: str, message: str):
    title = color(format_display_text(title, limit=15))
    message = format_display_text(message)
    announcement_display = f"{title}: {message}"
    print_item(index, total, announcement_display)


def archive_announcements(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting announcements...")
    announcements: list[DiscussionTopic] = collect(
        course.get_discussion_topics(only_announcements=True)
    )
    announcement_data: list[list[str]] = [
        process_announcement(announcement) for announcement in announcements
    ]
    data_frame = DataFrame(announcement_data, columns=["Title", "Message"])
    announcements_path = course_path / ANNOUNCEMENTS_PICKLE_FILE
    data_frame.to_pickle(announcements_path)
    total = len(announcement_data)
    if verbose:
        for index, announcement in enumerate(announcement_data):
            title, message = announcement
            if verbose:
                display_announcement(index, total, title, message)


def unpickle_announcements(course_path: Path, verbose: bool):
    data_frame = read_pickle(course_path / ANNOUNCEMENTS_PICKLE_FILE)
    announcements: list[list[str]] = data_frame.values.tolist()
    announcements_path = create_directory(course_path / "Announcements")
    total = len(announcements)
    for index, announcement in enumerate(announcements):
        title, message = announcement
        title_path = announcements_path / f"{title}.txt"
        with open(title_path, "w") as announcement_file:
            announcement_file.write(message)
        if verbose:
            display_announcement(index, total, title, message)


def archive_modules(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting modules...")
    modules_path = create_directory(course_path / "Modules")
    modules = collect(course.get_modules())
    module_total = len(modules)
    for module_index, module in enumerate(modules):
        module_name = format_name(module.name)
        if verbose:
            print_item(module_index, module_total, color(module_name, "blue"))
        module_path = create_directory(modules_path / module_name)
        items = collect(module.get_module_items())
        item_total = len(items)
        for item_index, item in enumerate(items):
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
                        f"Bearer {get_config_option('canvas_keys', 'canvas_prod_key')}"
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
                                response = get(file_url, headers=headers, stream=True)
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
            if verbose:
                print_item(
                    item_index,
                    item_total,
                    color(f"{item_title}: {file_content[:40]}", "yellow"),
                )


def archive_pages(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting pages...")
    pages_path = create_directory(course_path / "Pages")
    pages = collect(course.get_pages())
    total = len(pages)
    for index, page in enumerate(pages):
        title = format_name(page.title)
        page_path = pages_path / f"{title}.txt"
        body = strip_tags(page.show_latest_revision().body)
        with open(page_path, "w") as page_file:
            page_file.write(body)
        if verbose:
            print_item(index, total, f"{color(title)}: {color(body[:40], 'yellow')}")


def archive_syllabus(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting syllabus...")
    syllabus_path = create_directory(course_path / "Syllabus")
    syllabus = strip_tags(course.syllabus_body)
    if syllabus:
        with open(syllabus_path / "syllabus.txt", "w") as syllabus_file:
            syllabus_file.write(syllabus)
        if verbose:
            echo(f"SYLLABUS: {syllabus}")


def archive_assignment(
    assignment: Assignment,
    course_directory: Path,
    instance: Instance,
    index=0,
    total=0,
    verbose=False,
):
    assignment_name = format_name(assignment.name)
    assignment_directory = create_directory(course_directory / "Assignments")
    assignment_path = create_directory(assignment_directory / assignment_name)
    description_path = assignment_path / f"{assignment_name}_DESCRIPTION.txt"
    submissions_path = assignment_path / f"{assignment_name}_GRADES.csv"
    comments_path = create_directory(assignment_path / "Submission Comments")
    submissions = collect(assignment.get_submissions(include="submission_comments"))
    submissions = [
        process_submission(
            submission,
            instance,
            verbose,
            index,
            total,
            submission_index,
            len(submissions),
            assignment_name,
            assignment_path,
            comments_path,
        )
        for submission_index, submission in enumerate(submissions)
    ]
    try:
        description = assignment.description.replace("\n", " ")
        description = strip_tags(description).strip().split()
        description = " ".join(description)
    except Exception:
        description = ""
    columns = ["User", "Submission type", "Grade", "Score", "Grader"]
    submissions_data_frame = DataFrame(submissions, columns=columns)
    submissions_data_frame.to_csv(submissions_path, index=False)
    with open(description_path, "w") as assignment_file:
        assignment_file.write(description)
    if verbose:
        print_item(index, total, f"{color(assignment_name)}: {description}")


def archive_assignments(
    course: Course, course_path: Path, instance: Instance, verbose: bool
):
    echo(") Exporting assignments...")
    assignment_objects, assignment_total = get_assignments(course)
    if verbose:
        for index, assignment in enumerate(assignment_objects):
            archive_assignment(
                assignment, course_path, instance, index, assignment_total, verbose
            )
    else:
        with progressbar(assignment_objects, length=assignment_total) as progress:
            for assignment in progress:
                archive_assignment(assignment, course_path, instance)
    return assignment_objects


def archive_groups(course, course_directory, instance, verbose):
    echo(") Exporting groups...")
    categories = collect(course.get_group_categories())
    GROUP_DIRECTORY = create_directory(course_directory / "Groups")
    category_total = len(categories)
    for category_index, category in enumerate(categories):
        groups = collect(category.get_groups())
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
            files = collect(group.get_files())
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


def archive_grades(course, course_directory, assignment_objects, instance, verbose):
    def get_manual_posting(assignment):
        return "Manual Posting" if assignment.post_manually else ""

    echo(") Exporting grades...")
    enrollments = get_enrollments(course)
    if not assignment_objects:
        assignment_objects, _ = get_assignments(course)
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
    grades_path = create_directory(course_directory / "Grades") / "Grades.csv"
    rows = (
        [assignment_posted]
        + [assignment_points]
        + [
            archive_grade(enrollment, submissions, instance)
            for enrollment in enrollments
        ]
    )
    grade_book = DataFrame(rows, columns=columns)
    grade_book.to_csv(grades_path, index=False)
    if verbose:
        total = len(rows)
        for index, row in enumerate(rows):
            row = [str(item) for item in row]
            print_item(index, total, ", ".join(row))


def archive_discussion(
    discussion: DiscussionTopic,
    course_directory: Path,
    use_timestamp: bool,
    instance,
    csv_style=False,
    index=0,
    total=0,
    verbose=False,
):
    discussion_name = format_name(discussion.title)
    DISCUSSION_DIRECTORY = create_directory(course_directory / "Discussions")
    discussion_path = create_directory(DISCUSSION_DIRECTORY / discussion_name)
    description_path = discussion_path / f"{discussion_name}_DESCRIPTION.txt"
    entries = collect(discussion.get_topic_entries())
    if verbose and not entries:
        echo(f"==== DISCUSSION {index + 1} ====")
        echo("- NO ENTRIES")
    entries = [
        process_entry(
            entry,
            instance,
            verbose,
            index,
            total,
            entry_index,
            len(entries),
            discussion,
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
        entries_data_frame = DataFrame(entries, columns=columns)
        posts_path = discussion_path / f"{discussion_name}_POSTS.csv"
        entries_data_frame.to_csv(posts_path, index=False)
    else:
        posts_path = discussion_path / f"{discussion_name}_POSTS.txt"
        with open(posts_path, "w") as posts_file:
            for user, timestamp, message in entries:
                posts_file.write(f"\n{user}\n{timestamp}\n\n{message}\n")
    with open(description_path, "w") as description_file:
        description_file.write(description)


def archive_discussions(
    course: Course,
    course_path: Path,
    use_timestamp: bool,
    instance: Instance,
    verbose: bool,
):
    echo(") Exporting discussions...")
    discussion_topics, discussion_total = get_discussions(course)
    if verbose:
        for index, discussion in enumerate(discussion_topics):
            archive_discussion(
                discussion,
                course_path,
                use_timestamp,
                instance,
                index=index,
                total=discussion_total,
                verbose=verbose,
            )
    else:
        with progressbar(discussion_topics, length=discussion_total) as progress:
            for discussion in progress:
                archive_discussion(
                    discussion, course_path, use_timestamp, instance=instance
                )


def archive_grade(
    enrollment: Enrollment,
    submissions: list[tuple[str, list[tuple[int, int]]]],
    instance: Instance,
) -> list:
    def get_score_from_submissions(submissions: list[tuple[int, int]], user_id: str):
        return next(item[1] for item in submissions if item[0] == user_id)

    user_id = enrollment.user_id
    user = enrollment.user
    section_id = get_section(enrollment.course_section_id, instance=instance).name
    student_data = [
        user["sortable_name"],
        user_id,
        user["sis_user_id"],
        user["login_id"],
        section_id,
    ]
    submission_scores = [
        get_score_from_submissions(submission[1], user_id) for submission in submissions
    ]
    total_scores = [
        enrollment.grades["current_score"],
        enrollment.grades["unposted_current_score"],
        enrollment.grades["final_score"],
        enrollment.grades["unposted_final_score"],
        enrollment.grades["current_grade"],
        enrollment.grades["unposted_current_grade"],
        enrollment.grades["final_grade"],
        enrollment.grades["unposted_final_grade"],
    ]
    return student_data + submission_scores + total_scores


def archive_quiz(course, quiz, verbose, course_directory, index=0, total=0):
    title = format_name(quiz.title)
    if verbose:
        print_item(index, total, f"{title}")
    description = strip_tags(quiz.description) if quiz.description else quiz.description
    if verbose:
        echo("\t> Getting questions...")
    questions = [
        [
            strip_tags(question.question_text),
            ", ".join([answer["text"] for answer in question.answers]),
        ]
        for question in quiz.get_questions()
    ]
    assignment = course.get_assignment(quiz.assignment_id)
    if verbose:
        echo("\t> Getting submissions...")
    submissions = collect(
        assignment.get_submissions(include=["submission_history", "user"])
    )
    QUIZ_DIRECTORY = create_directory(course_directory / "Quizzes")
    quiz_path = create_directory(QUIZ_DIRECTORY / title)
    description_path = quiz_path / f"{title}_DESCRIPTION.txt"
    questions_path = quiz_path / f"{title}_QUESTIONS.csv"
    scores_path = quiz_path / f"{title}_SCORES.csv"
    submissions_path = create_directory(quiz_path / "Submissions")
    submission_histories = [
        (submission.user["name"], submission.submission_history)
        for submission in submissions
    ]
    submissions_total = len(submission_histories)
    for index, submission_history in enumerate(submission_histories):
        name, histories = submission_history
        if verbose:
            print_item(
                index,
                submissions_total,
                f"Getting submission data for {color(name)}...",
                prefix="\t\t*",
            )
        for history in histories:
            submission_data = (
                [
                    [
                        name,
                        submission_data["correct"],
                        submission_data["points"],
                        submission_data["question_id"],
                        strip_tags(submission_data["text"]),
                    ]
                    for submission_data in history["submission_data"]
                ]
                if "submission_data" in history
                else []
            )
            submission_data = DataFrame(
                submission_data,
                columns=["Student", "Correct", "Points", "Question ID", "Text"],
            )
            submission_data_path = (
                submissions_path / f"{name}_submissions_{history['id']}.csv"
            )
            submission_data.to_csv(submission_data_path, index=False)
    if verbose:
        echo("\t> Collecting user scores...")
    user_scores = [
        [
            submission.user["name"],
            round(submission.score, 2) if submission.score else submission.score,
        ]
        for submission in submissions
    ]
    user_scores = DataFrame(user_scores, columns=["Student", "Score"])
    questions = DataFrame(questions, columns=["Question", "Answers"])
    user_scores.to_csv(scores_path, index=False)
    questions.to_csv(questions_path, index=False)
    if description:
        if verbose:
            echo("\t> Getting description...")
        with open(description_path, "w") as description_file:
            description_file.write(description)


def archive_quizzes(
    course: Course, course_path: Path, instance: Instance, verbose: bool
):
    echo(") Exporting quizzes...")
    quiz_objects, quiz_total = get_quizzes(course)
    if verbose:
        total = len(quiz_objects)
        for index, quiz in enumerate(quiz_objects):
            archive_quiz(course, quiz, verbose, course_path, index, total)
    else:
        with progressbar(quiz_objects, length=quiz_total) as progress:
            for quiz in progress:
                archive_quiz(quiz, verbose, course_path, instance)


def process_criterion_rating(rating):
    points = rating["points"]
    description = rating["description"]
    long_description = rating["long_description"] or ""
    return f"{points} {description} {long_description}"


def process_criterion(criterion):
    description = criterion["description"]
    ratings = criterion["ratings"]
    ratings = [process_criterion_rating(rating) for rating in ratings]
    ratings = " / ".join(ratings)
    points = criterion["points"]
    return [description, ratings, points]


def archive_rubric(
    rubric: Rubric, course_directory: Path, verbose: bool, index=0, total=0
):
    title = rubric.title.strip()
    if verbose:
        print_item(index, total, color(title))
    rubric_directory = create_directory(course_directory / "Rubrics")
    rubric_path = rubric_directory / f"{title}.csv"
    criteria = [process_criterion(criterion) for criterion in rubric.data]
    data_frame = DataFrame(criteria, columns=["Criteria", "Ratings", "Pts"])
    data_frame.to_csv(rubric_path, index=False)


def archive_rubrics(course: Course, course_path: Path, verbose: bool):
    echo(") Exporting rubrics...")
    rubric_objects, rubric_total = get_rubrics(course)
    if verbose:
        total = len(rubric_objects)
        for index, rubric in enumerate(rubric_objects):
            archive_rubric(rubric, course_path, verbose, index, total)
    else:
        with progressbar(rubric_objects, length=rubric_total) as progress:
            for rubric in progress:
                archive_rubric(rubric, course_path, verbose)


def archive_main(
    course_id: int,
    instance_name: str,
    verbose: bool,
    use_timestamp: bool,
    content: Optional[bool],
    announcements: Optional[bool],
    modules: Optional[bool],
    pages: Optional[bool],
    syllabus: Optional[bool],
    assignments: Optional[bool],
    groups: Optional[bool],
    discussions: Optional[bool],
    grades: Optional[bool],
    quizzes: Optional[bool],
    rubrics: Optional[bool],
):
    archive_all = not any(
        [
            content,
            announcements,
            modules,
            pages,
            syllabus,
            assignments,
            groups,
            discussions,
            grades,
            quizzes,
            rubrics,
        ]
    )
    instance = validate_instance_name(instance_name)
    switch_logger_file(LOGS, "archive", instance.name)
    course = get_course(course_id, include=["syllabus_body"], instance=instance)
    course_name = f"{format_name(course.name)} ({course.id})"
    echo(f") Archiving course: {color(course_name, 'blue')}...")
    course_path = create_directory(RESULTS / course_name)
    assignment_objects: list[Assignment] = list()
    if should_run_option(content, archive_all):
        archive_content(course, course_path, instance, verbose)
    if should_run_option(announcements, archive_all):
        archive_announcements(course, course_path, verbose)
    if should_run_option(modules, archive_all):
        archive_modules(course, course_path, verbose)
    if should_run_option(pages, archive_all):
        archive_pages(course, course_path, verbose)
    if should_run_option(syllabus, archive_all):
        archive_syllabus(course, course_path, verbose)
    if should_run_option(assignments, archive_all):
        assignment_objects = archive_assignments(course, course_path, instance, verbose)
    if should_run_option(groups, archive_all):
        archive_groups(course, course_path, instance, verbose)
    if should_run_option(discussions, archive_all):
        archive_discussions(course, course_path, use_timestamp, instance, verbose)
    if should_run_option(grades, archive_all):
        archive_grades(course, course_path, assignment_objects, instance, verbose)
    if should_run_option(quizzes, archive_all):
        archive_quizzes(course, course_path, instance, verbose)
    if should_run_option(rubrics, archive_all):
        archive_rubrics(course, course_path, verbose)
    echo("COMPELTE")
