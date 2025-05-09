from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import random

from api.models import Course, Lesson, Option, Question, Quiz

class Command(BaseCommand):
    help = 'Seeds the database with sample courses, lessons, quizzes, questions, and options.'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('No users found. Please create a user first.'))
            return

        for i in range(5):
            course = Course.objects.create(
                user=user,
                title=f"Course {i + 1}",
                description=f"This is the description for Course {i + 1}."
            )
            self.stdout.write(self.style.SUCCESS(f'Created {course.title}'))

            for j in range(10):
                lesson = Lesson.objects.create(
                    course=course,
                    title=f"Lesson {j + 1} of {course.title}",
                    content=f"Content for Lesson {j + 1} in {course.title}."
                )
                self.stdout.write(self.style.SUCCESS(f'  Created {lesson.title}'))

                quiz = Quiz.objects.create(
                    lesson=lesson,
                    title=f"Quiz for {lesson.title}"
                )
                self.stdout.write(self.style.SUCCESS(f'    Created {quiz.title}'))

                for q in range(3):  # 3 questions per quiz
                    question = Question.objects.create(
                        quiz=quiz,
                        text=f"Question {q + 1} for {quiz.title}?"
                    )

                    correct_option = random.randint(1, 4)
                    for o in range(1, 5):  # 4 options per question
                        Option.objects.create(
                            question=question,
                            text=f"Option {o} for Question {q + 1}",
                            is_correct=(o == correct_option)
                        )

                    self.stdout.write(self.style.SUCCESS(f'      Created Question {q + 1} with options'))

        self.stdout.write(self.style.SUCCESS('Database seeding complete!'))
