from datetime import datetime, timedelta
from pathlib import Path

from pandas import DataFrame, read_csv
from typer import Exit, echo

from penn_canvas.helpers import BOX_PATH, TODAY_AS_Y_M_D, color, get_canvas

COMMAND = "Investigate"
RESULTS = BOX_PATH / "OGC Request"


def get_investigate_input_file():
    input_file = next(
        (
            csv_file
            for csv_file in RESULTS.glob("*csv")
            if "investigate" in csv_file.name and TODAY_AS_Y_M_D in csv_file.name
        ),
        None,
    )
    if not input_file:
        echo(
            "An \"investigate csv file matching today's date was not found. Please add"
            " one and try again."
        )
        raise Exit()
    else:
        return input_file


def format_timestamp(timestamp):
    if timestamp:
        date = datetime.fromisoformat(timestamp.replace("Z", ""))
        return date.strftime("%b %d, %Y (%I:%M:%S %p)")
    else:
        return None


def get_submitted_at_date(submission):
    try:
        return format_timestamp(submission.submitted_at)
    except Exception:
        return None


def get_grader(grader_id, canvas):
    try:
        return canvas.get_user(grader_id) if grader_id > 0 else None
    except Exception:
        return None


def process_conversation(
    conversation, course_ids, index, total, user_canvas_instance, canvas
):
    conversation = user_canvas_instance.get_conversation(conversation)
    course_id = "".join(
        character for character in conversation.context_code if character.isnumeric()
    )
    course_ids = [str(course_id) for course_id in course_ids]
    if course_id not in course_ids:
        return (None, None)
    subject = conversation.subject
    participants = ", ".join(
        [participant["full_name"] for participant in conversation.participants]
    )
    course_name = conversation.context_name
    messages = "\n\n".join(
        [
            f"{canvas.get_user(message['author_id']).name}"
            f"\n{format_timestamp(message['created_at'])}\n\n{message['body']}"
            for message in conversation.messages
        ]
    )
    course_path = RESULTS / course_name.strip().replace(" ", "_").replace("/", "-")
    if not course_path.exists():
        Path.mkdir(course_path)
    conversation_path = course_path / "conversations.txt"
    data = (
        conversation_path,
        f"{subject}\n{participants}\n{course_name}\n\n{messages}\n\n",
    )
    echo(f" - ({index + 1:,}/{total:,}) {color(subject)}")
    return data


def process_assignment(assignment, user_id, canvas, index, total, course_path):
    name = assignment.name
    submission_types = ", ".join(
        [assignment.replace("_", " ") for assignment in assignment.submission_types]
    )
    due_date = format_timestamp(assignment.due_at)
    unlock_date = format_timestamp(assignment.unlock_at)
    lock_date = format_timestamp(assignment.lock_at)
    points_possible = assignment.points_possible
    submission = next(
        submission
        for submission in assignment.get_submissions(include="submission_comments")
        if submission.user_id == user_id
    )
    submitted_at = get_submitted_at_date(submission)
    attempt = submission.attempt
    grade = submission.grade
    grade_matches_current_submission = submission.grade_matches_current_submission
    score = submission.score
    grader_id = get_grader(submission.grader_id, canvas)
    graded_at = format_timestamp(submission.graded_at)
    late = submission.late
    excused = submission.excused
    missing = submission.missing
    late_policy_status = submission.late_policy_status
    points_deducted = submission.points_deducted
    seconds_late = timedelta(seconds=submission.seconds_late)
    extra_attempts = submission.extra_attempts
    submission_comments = submission.submission_comments
    if submission_comments:
        comments_path = course_path / "assignment_submission_comments.csv"
        comments = list()
        for comment in submission_comments:
            author = comment["author"]["display_name"]
            message = comment["comment"]
            created_at = format_timestamp(comment["created_at"])
            comments.append([author, created_at, message])
        comments = DataFrame(comments, columns=["Name", "Created At", "Comment"])
        comments.to_csv(comments_path, index=False)
    else:
        submission_comments = None
    assignment_row = [
        name,
        submission_types,
        due_date,
        unlock_date,
        lock_date,
        points_possible,
        submitted_at,
        attempt,
        grade,
        grade_matches_current_submission,
        score,
        grader_id,
        graded_at,
        late,
        excused,
        missing,
        late_policy_status,
        points_deducted,
        seconds_late,
        extra_attempts,
        submission_comments,
    ]
    late_display = "LATE" if late else "ON TIME"
    echo(
        f" - ({index + 1:,}/{total:,}) {color(name)}:"
        f" {color(late_display, 'red' if late else 'green')}"
    )
    return assignment_row


def process_discussion(discussion, user_id, index, total):
    title = discussion.title
    created_at = discussion.created_at
    posted_at = discussion.posted_at
    entry = next(
        (entry for entry in discussion.get_topic_entries() if entry.user_id == user_id),
        None,
    )
    lock_at = discussion.lock_at
    entry_created_at = format_timestamp(entry.created_at) if entry else ""
    entry_updated_at = format_timestamp(entry.updated_at) if entry else ""
    discussion_row = [
        title,
        created_at,
        posted_at,
        lock_at,
        entry_created_at,
        entry_updated_at,
    ]
    echo(
        f" - ({index + 1:,}/{total:,}) {color(title)}:"
        f" {color(entry_created_at, 'yellow')}"
    )
    return discussion_row


def process_quiz(quiz, user_id, index, total):
    title = quiz.title
    due_at = format_timestamp(quiz.due_at)
    unlock_at = format_timestamp(quiz.unlock_at)
    lock_at = format_timestamp(quiz.lock_at)
    points_possible = quiz.points_possible
    allowed_attempts = quiz.allowed_attempts
    time_limit = quiz.time_limit
    submission = next(
        (
            submission
            for submission in quiz.get_submissions()
            if submission.user_id == user_id
        ),
        None,
    )
    end_at = format_timestamp(submission.end_at) if submission else ""
    started_at = format_timestamp(submission.started_at) if submission else ""
    finished_at = format_timestamp(submission.finished_at) if submission else ""
    time_spent = timedelta(seconds=submission.time_spent) if submission else ""
    extra_time = submission.extra_time if submission else ""
    attempt = submission.attempt if submission else ""
    attempts_left = submission.attempts_left if submission else ""
    extra_attempts = submission.extra_attempts if submission else ""
    overdue_and_needs_submission = (
        submission.overdue_and_needs_submission if submission else ""
    )
    excused = getattr(submission, "excused?") if submission else ""
    score = submission.score if submission else ""
    score_before_regrade = submission.score_before_regrade if submission else ""
    quiz_row = [
        title,
        due_at,
        unlock_at,
        lock_at,
        points_possible,
        allowed_attempts,
        time_limit,
        end_at,
        started_at,
        finished_at,
        time_spent,
        extra_time,
        attempt,
        attempts_left,
        extra_attempts,
        overdue_and_needs_submission,
        excused,
        score,
        score_before_regrade,
    ]
    echo(
        f" - ({index + 1:,}/{total:,}) {color(title)}:"
        f" {color(f'{score}/{points_possible}', 'green' if score else 'red')}"
    )
    return quiz_row


def investigate_main():
    input_file = get_investigate_input_file()
    try:
        user_id = next(iter(read_csv(input_file)["Canvas User ID"].tolist()))
        course_ids = read_csv(input_file)["Canvas Course ID"].tolist()
    except Exception:
        echo("The input file is not formatted correctly. Please update and try again.")
        raise Exit()
    canvas = get_canvas()
    canvas_user = canvas.get_user(user_id)
    echo(f"Investigating student {canvas_user.name}...")
    echo("\tGetting conversations...")
    user_canvas_instance = get_canvas(
        override_key=input("Please enter the user's API Token: ")
    )
    conversations = [
        conversation for conversation in user_canvas_instance.get_conversations()
    ]
    conversations = [
        process_conversation(
            conversation,
            course_ids,
            index,
            len(conversations),
            user_canvas_instance,
            canvas,
        )
        for index, conversation in enumerate(conversations)
    ]
    for conversation in conversations:
        conversation_path, data = conversation
        if conversation_path and data:
            with open(conversation_path, "a+") as conversation_file:
                conversation_file.write(data)
    return
    for course_id in course_ids:
        course = canvas.get_course(course_id)
        echo(f"Processing {course.name}...")
        course_path = RESULTS / course.name.strip().replace(" ", "_").replace("/", "-")
        if not course_path.exists():
            Path.mkdir(course_path)
        assignments_path = course_path / "assignments.csv"
        discussions_path = course_path / "discussions.csv"
        quizzes_path = course_path / "quizzes.csv"
        echo("\tGetting assignments...")
        assignments = [assignment for assignment in course.get_assignments()]
        assignments_rows = [
            process_assignment(
                assignment, user_id, canvas, index, len(assignments), course_path
            )
            for index, assignment in enumerate(assignments)
        ]
        assignments = DataFrame(
            assignments_rows,
            columns=[
                "Name",
                "Submission Types",
                "Due Date",
                "Unlock Date",
                "Lock Date",
                "Points Possible",
                "Submitted At Date",
                "Attempt",
                "Grade",
                "Grade Matches Current Submission",
                "Score",
                "Grader ID",
                "Graded At Date",
                "Late",
                "Excused",
                "Missing",
                "Late Policy Status",
                "Points Deducted",
                "Time Late",
                "Extra Attempts",
                "Submission Comments",
            ],
        )
        assignments.to_csv(assignments_path, index=False)
        echo("\tGetting discussions...")
        discussions = [discussion for discussion in course.get_discussion_topics()]
        discussions = [
            process_discussion(discussion, user_id, index, len(discussions))
            for index, discussion in enumerate(discussions)
        ]
        discussions = DataFrame(
            discussions,
            columns=[
                "Name",
                "Created At",
                "Posted At",
                "Lock Date",
                "Entry Created At",
                "Entry Updated At",
            ],
        )
        discussions.to_csv(discussions_path, index=False)
        echo("\tGetting quizzes...")
        quizzes = [quiz for quiz in course.get_quizzes()]
        quizzes = [
            process_quiz(quiz, user_id, index, len(quizzes))
            for index, quiz in enumerate(quizzes)
        ]
        quizzes = DataFrame(
            quizzes,
            columns=[
                "Name",
                "Due Date",
                "Unlock Date",
                "Lock Date",
                "Points Possible",
                "Allowed Attempts",
                "Time Limit",
                "End At",
                "Started At",
                "Finished At",
                "Time Spent",
                "Extra Time",
                "Attempt",
                "Attempts Left",
                "Extra Attempts",
                "Overdue And Needs Submission",
                "Excused",
                "Score",
                "Score Before Regrade",
            ],
        )
        quizzes.to_csv(quizzes_path, index=False)
