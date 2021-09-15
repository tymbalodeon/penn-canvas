from .helpers import get_canvas


def count_surveys(inputfile="survey_input.csv", outputfile="RESULT_surveys.csv"):
    def sort_quizzes(quizzes, quiz_type, published):
        return len(
            [
                quiz
                for quiz in quizzes
                if quiz.quiz_type == quiz_type and bool(quiz.published) is published
            ]
        )

    canvas = get_canvas()
    courses = []

    for course in courses:
        canvas_course_id, course_id, short_name, account, term, status = course
        course = canvas.get_course(canvas_course_id)
        quizzes = course.get_quizzes()
        published_ungraded_quizzes = sort_quizzes(quizzes, "survey", True)
        unpublished_ungraded_quizzes = sort_quizzes(quizzes, "survey", False)
        published_graded_quizzes = sort_quizzes(quizzes, "graded_survey", True)
        unpublished_graded_quizzes = sort_quizzes(quizzes, "graded_survey", False)
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
