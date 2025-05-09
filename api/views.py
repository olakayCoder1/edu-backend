from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Max
from django.shortcuts import get_object_or_404

from .models import Course, Lesson, QuizResponse, QuizAttempt, UserProgress
from .serializers import (
    CourseSerializer,
    LessonSerializer,
    QuizAttemptSerializer,
    UserProgressSerializer,
    QuizAttemptResultSerializer,
    QuizSubmitSerializer,
)


class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Course.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        course = serializer.save(user=self.request.user)
        
        # Create initial progress for this course
        if course.lessons.exists():
            first_lesson = course.lessons.order_by('order').first()
            UserProgress.objects.create(
                user=self.request.user,
                course=course,
                current_lesson=first_lesson
            )


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Lesson.objects.filter(course__user=self.request.user)


class UserProgressViewSet(viewsets.ModelViewSet):
    serializer_class = UserProgressSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return UserProgress.objects.filter(user=self.request.user)


class QuizAttemptViewSet(viewsets.ModelViewSet):
    serializer_class = QuizAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return QuizAttempt.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        quiz = serializer.validated_data['quiz']
        
        # Get the next attempt number
        last_attempt = QuizAttempt.objects.filter(
            user=self.request.user,
            quiz=quiz
        ).aggregate(max_attempt=Max('attempt_number'))
        
        next_attempt = (last_attempt['max_attempt'] or 0) + 1
        
        serializer.save(
            user=self.request.user,
            attempt_number=next_attempt,
            status='in_progress'
        )
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit quiz responses and calculate score"""
        quiz_attempt = self.get_object()
        
        # Validate the quiz attempt is still in progress
        if quiz_attempt.status != 'in_progress':
            return Response(
                {"detail": "This quiz attempt has already been submitted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = QuizSubmitSerializer(data=request.data)
        if serializer.is_valid():
            # Create each response
            correct_count = 0
            total_questions = quiz_attempt.quiz.questions.count()
            
            for response_data in serializer.validated_data['responses']:
                question = response_data['question']
                option = response_data['selected_option']
                
                # Check if response is correct
                is_correct = option.is_correct
                if is_correct:
                    correct_count += 1
                
                # Save the response
                QuizResponse.objects.create(
                    attempt=quiz_attempt,
                    question=question,
                    selected_option=option,
                    is_correct=is_correct
                )
            
            # Calculate score as percentage
            score = int((correct_count / total_questions) * 100) if total_questions > 0 else 0
            
            # Update quiz attempt
            quiz_attempt.score = score
            quiz_attempt.completed_at = timezone.now()
            
            # Check if passed
            if score >= quiz_attempt.quiz.passing_score:
                quiz_attempt.status = 'passed'
                
                # Update user progress if they passed the quiz
                lesson = quiz_attempt.quiz.lesson
                course = lesson.course
                
                # Get user progress for this course
                progress, created = UserProgress.objects.get_or_create(
                    user=self.request.user,
                    course=course,
                    defaults={'current_lesson': lesson}
                )
                
                # Mark current lesson as completed
                progress.completed_lessons.add(lesson)
                
                # Move to next lesson if available
                next_lesson = Lesson.objects.filter(
                    course=course,
                    order__gt=lesson.order
                ).order_by('order').first()
                
                if next_lesson:
                    progress.current_lesson = next_lesson
                    progress.save()
            else:
                quiz_attempt.status = 'failed'
            
            quiz_attempt.save()
            
            # Return the results
            return Response(
                QuizAttemptResultSerializer(quiz_attempt).data,
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessonAccessAPIView(generics.RetrieveAPIView):
    """API view to check if a user can access a specific lesson"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = lesson.course
        
        # Ensure the user has access to this course
        if course.user != request.user:
            return Response(
                {"detail": "You do not have access to this course."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user progress
        progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={'current_lesson': course.lessons.order_by('order').first()}
        )
        
        # The user can access:
        # 1. Their current lesson
        # 2. Any completed lesson
        # 3. The first lesson of the course
        first_lesson = course.lessons.order_by('order').first()
        can_access = (
            lesson == progress.current_lesson or
            lesson in progress.completed_lessons.all() or
            lesson == first_lesson
        )
        
        if not can_access:
            # Check if the previous lesson has a passed quiz
            previous_lessons = Lesson.objects.filter(
                course=course,
                order__lt=lesson.order
            ).order_by('-order')
            
            if previous_lessons.exists():
                prev_lesson = previous_lessons.first()
                prev_quizzes = prev_lesson.quizzes.all()
                
                if prev_quizzes.exists():
                    # Check if any quiz in the previous lesson has been passed
                    for quiz in prev_quizzes:
                        passed_attempt = QuizAttempt.objects.filter(
                            user=request.user,
                            quiz=quiz,
                            status='passed'
                        ).exists()
                        
                        if passed_attempt:
                            can_access = True
                            break
            
        response_data = {
            "can_access": can_access,
            "current_lesson_id": progress.current_lesson.id,
            "completed_lesson_ids": list(progress.completed_lessons.values_list('id', flat=True))
        }
        
        return Response(response_data)