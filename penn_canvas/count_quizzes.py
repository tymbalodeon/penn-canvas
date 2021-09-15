from .helpers import get_canvas


def filter_and_count_quizzes(quizzes, quiz_type, published):
    return len(
        [
            quiz
            for quiz in quizzes
            if quiz.quiz_type == quiz_type and quiz.published is published
        ]
    )


def count_surveys():

    canvas = get_canvas()
    courses = []

    for course in courses:
        canvas_course_id, course_id, short_name, account, term, status = course
        course = canvas.get_course(canvas_course_id)
        quizzes = course.get_quizzes()
        published_ungraded_quizzes = filter_and_count_quizzes(quizzes, "survey", True)
        unpublished_ungraded_quizzes = filter_and_count_quizzes(
            quizzes, "survey", False
        )
        published_graded_quizzes = filter_and_count_quizzes(
            quizzes, "graded_survey", True
        )
        unpublished_graded_quizzes = filter_and_count_quizzes(
            quizzes, "graded_survey", False
        )
        total_quizzes = (
            published_ungraded_quizzes
            + unpublished_ungraded_quizzes
            + published_graded_quizzes
            + unpublished_graded_quizzes
        )

        print(
            canvas_course_id,
            course_id,
            account,
            term,
            status,
            published_ungraded_quizzes,
            unpublished_ungraded_quizzes,
            published_graded_quizzes,
            unpublished_graded_quizzes,
            total_quizzes,
        )
