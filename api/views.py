from langchain_google_genai import ChatGoogleGenerativeAI
from rest_framework import viewsets, status, generics, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Max,Avg,Q
from django.shortcuts import get_object_or_404
import os
from dotenv import load_dotenv
import tempfile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from api.helpers.module_generation import LangGraphAgent
from api.helpers.user_service import UserService
from utils.response.response_format import paginate_success_response_with_serializer, success_response,bad_request_response, internal_server_error_response
from django.contrib.auth import get_user_model
from datetime import timedelta
import csv
from django.http import HttpResponse
import io
from .models import Course, Lesson, Option, Question, Quiz, QuizResponse, QuizAttempt, UserProgress
from .serializers import (
    CourseDetailSerializer,
    CourseSerializer,
    CourseUploadSerializer,
    LessonCompletionRateSerializer,
    LessonSerializer,
    QuizAttemptSerializer,
    StudentSerializer,
    UserProgressSerializer,
    QuizAttemptResultSerializer,
    QuizSubmitSerializer,
    UserSerializer, 
    UserDetailSerializer,
    UserCreateSerializer,
    UserStatusUpdateSerializer,
    BulkUserActionSerializer
)
load_dotenv()
from django.db import transaction

class CourseViewSet(viewsets.ModelViewSet):
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Course.objects.all().order_by('-created_at') 
    
    # def get_queryset(self):
    #     return Course.objects.filter(user=self.request.user)

    # override the list endpoint
    def list(self, request, *args, **kwargs):
        return success_response(
            data=self.serializer_class(self.get_queryset(),many=True,context={'request': request}).data
        )

    

class CourseViewSet1(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    queryset = Course.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    # def get_queryset(self):
    #     return Course.objects.filter(user=self.request.user)
    
    def list(self, request, *args, **kwargs):
        return success_response(
            data=self.get_serializer_class()(self.get_queryset(), many=True, context={'request': request}).data
        )
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={'request': request})
        return success_response(data=serializer.data)



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
        
        return bad_request_response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


# Let's create an endpoint to mark a lesson as completed

class CompleteLessonView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id, lesson_id):
        course = get_object_or_404(Course, id=course_id)
        lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
        
        # Get or create progress record
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={'current_lesson': lesson}
        )
        
        # Add to completed lessons
        user_progress.completed_lessons.add(lesson)
        
        # Update current lesson to next lesson if available
        try:
            next_lesson = Lesson.objects.filter(
                course=course
            ).order_by('created_at')
            
            found = False
            for les in next_lesson:
                if found:
                    user_progress.current_lesson = les
                    user_progress.save()
                    break

                if les.id == lesson.id:
                    found = True
                    
        except Lesson.DoesNotExist:
            # No next lesson, this was the last one
            pass
        
        # Return updated lesson data
        serializer = LessonSerializer(lesson, context={'request': request})
        return success_response(
            message="Lesson marked as completed",
            data=serializer.data
        )


class InProgressCoursesView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]  # Ensure the user is authenticated
    serializer_class = CourseSerializer

    def get_queryset(self):
        # Get the authenticated user
        user = self.request.user
        
        # Check if there is a UserProgress entry for the user and course, and filter based on that
        in_progress_courses = Course.objects.filter(
            user_progress__user=user,  # Filter using the related UserProgress model
            user_progress__current_lesson__isnull=False  # Ensure current lesson is not null
        )
        
        return in_progress_courses


    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={'request': request})
        return success_response(data=serializer.data)
    

    def list(self, request, *args, **kwargs):
        return success_response(
            data=self.get_serializer_class()(self.get_queryset(), many=True, context={'request': request}).data
        )

# class CourseUploadView(generics.GenericAPIView):
#     permission_classes = [permissions.IsAuthenticated] 
#     serializer_class = CourseUploadSerializer

#     def post(self, request):

#         serializer = self.serializer_class(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         title = serializer.validated_data['title']
#         description = serializer.validated_data['description']
#         pdf_file = serializer.validated_data['pdf_file']
#         return success_response(
#             message="Course uploaded successfully",
#         )




class CourseUploadView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CourseUploadSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        title = serializer.validated_data['title']
        description = serializer.validated_data['description']
        pdf_file = serializer.validated_data['pdf_file']

        try:
            with transaction.atomic():
                course = Course.objects.create(
                    title=title,
                    description=description,
                    user=request.user
                )

                pdf_path = default_storage.save(
                    f'courses/{course.id}/{pdf_file.name}',
                    ContentFile(pdf_file.read())
                )
                course.file_path = pdf_path
                course.save()

                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    pdf_file.seek(0)
                    temp_file.write(pdf_file.read())
                    temp_path = temp_file.name

                model = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    temperature=0.2,
                    api_key=os.getenv('GOOGLE_API_KEY')
                )

                hints_db = {}
                agent = LangGraphAgent(model, hints_db=hints_db, max_chunk_size=1500)

                modules_data = agent.process_document(temp_path)

                for module_data in modules_data:
                    lesson = Lesson.objects.create(
                        course=course,
                        title=module_data['name'],
                        summary=module_data.get('summary', ''),
                        content=module_data['content']
                    )
                    lesson.prerequisites = module_data.get('prerequisites', [])
                    lesson.save()

                    try:
                        quiz_questions = agent.quiz_generator.generate_quiz(module_data)

                        if quiz_questions:
                            quiz = Quiz.objects.create(
                                lesson=lesson,
                                title=f"Quiz: {lesson.title}"
                            )

                            for q_data in quiz_questions:
                                question = Question.objects.create(
                                    quiz=quiz,
                                    text=q_data['question'],
                                    # difficulty=q_data.get('difficulty', 3)
                                )
                                for option_text in q_data.get('options', []):
                                    is_correct = True if option_text == q_data.get('answer') else False

                                # for i, option_text in enumerate(q_data.get('options', [])):
                                #     is_correct = (i == q_data.get('answer', 0))
                                    Option.objects.create(
                                        question=question,
                                        text=option_text,
                                        is_correct=is_correct
                                    )
                    except Exception as e:
                        print(f"Error generating quiz for lesson {lesson.title}: {str(e)}")

                os.unlink(temp_path)

                return success_response(
                    message="Course uploaded and processed successfully",
                    data={
                        "course_id": course.id,
                        "lesson_count": Lesson.objects.filter(course=course).count()
                    }
                )

        except Exception as e:
            print(e)
            return internal_server_error_response(
                message=f"Course upload failed"
            )




User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management operations
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_queryset(self):
        """
        Get filtered users based on query parameters
        """
        # Build filters
        filters = {}
        
        # Role filter
        role = self.request.query_params.get('role')
        if role and role != 'all':
            filters['role'] = role
            
        # Status filter
        status = self.request.query_params.get('status')
        if status and status != 'all':
            filters['status'] = status
            
        # Search term
        search = self.request.query_params.get('search')
        
        # Get users from service
        return UserService.get_all_users(filters, search)
    
    def list(self, request, *args, **kwargs):
        """
        List users with pagination and formatted response
        """
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            # Format each user for frontend
            users = [UserService.format_user_for_frontend(user) for user in page]
            return self.get_paginated_response(users)
        
        # If pagination is not used
        users = [UserService.format_user_for_frontend(user) for user in queryset]
        return Response(users)
    
    def retrieve(self, request, *args, **kwargs):
        """
        Get user details by ID
        """
        instance = self.get_object()
        serializer = UserDetailSerializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """
        Create a new user
        """
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user, success, message = UserService.create_user(serializer.validated_data)
            
            if success:
                return Response(
                    {
                        'status': True,
                        'message': message,
                        'user': UserService.format_user_for_frontend(user)
                    }, 
                    status=status.HTTP_201_CREATED
                )
            else:
                return Response(
                    {'status': False, 'message': message}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(
            {'status': False, 'message': serializer.errors}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def update(self, request, *args, **kwargs):
        """
        Update user details
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = UserDetailSerializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            user, success, message = UserService.update_user(
                str(instance.id), 
                serializer.validated_data
            )
            
            if success:
                return Response(
                    {
                        'status': True,
                        'message': message,
                        'user': UserService.format_user_for_frontend(user)
                    }
                )
            else:
                return Response(
                    {'status': False, 'message': message}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(
            {'status': False, 'message': serializer.errors}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete a user
        """
        instance = self.get_object()
        success, message = UserService.delete_user(str(instance.id))
        
        if success:
            return Response(
                {'status': True, 'message': message},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'status': False, 'message': message},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, *args, **kwargs):
        """
        Update user status (approve, reject, deactivate)
        """
        instance = self.get_object()
        serializer = UserStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            status_value = serializer.validated_data['status']
            update_data = {'status': status_value}
            
            user, success, message = UserService.update_user(
                str(instance.id),
                update_data
            )
            
            if success:
                return Response({
                    'status': True,
                    'message': message,
                    'user': UserService.format_user_for_frontend(user)
                })
            else:
                return Response(
                    {'status': False, 'message': message},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(
            {'status': False, 'message': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['post'])
    def bulk_update_status(self, request, *args, **kwargs):
        """
        Update status for multiple users
        """
        serializer = BulkUserActionSerializer(data=request.data)
        
        if serializer.is_valid():
            user_ids = serializer.validated_data['user_ids']
            status_value = serializer.validated_data['status']
            
            updated_count, failed_ids, message = UserService.bulk_update_status(
                user_ids,
                status_value
            )
            
            return Response({
                'status': True,
                'message': message,
                'updated_count': updated_count,
                'failed_ids': failed_ids
            })
        
        return Response(
            {'status': False, 'message': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['get'])
    def stats(self, request, *args, **kwargs):
        """
        Get user statistics
        """
        stats = UserService.get_user_stats()
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def approve_all_pending(self, request, *args, **kwargs):
        """
        Approve all pending users
        """
        pending_users = User.objects.filter(is_verify=False)
        user_ids = [str(user.id) for user in pending_users]
        
        updated_count, failed_ids, message = UserService.bulk_update_status(
            user_ids,
            'approved'
        )
        
        return Response({
            'status': True,
            'message': f"Approved {updated_count} pending users",
            'updated_count': updated_count,
            'failed_ids': failed_ids
        })
    
    @action(detail=False, methods=['post'])
    def deactivate_inactive(self, request, *args, **kwargs):
        """
        Deactivate users who haven't been active in the last 60 days
        """
        # Calculate cutoff date (60 days ago)
        cutoff_date = timezone.now() - timedelta(days=60)
        
        # Find users with no activity since cutoff date
        inactive_users = User.objects.filter(updated_at__lt=cutoff_date, is_active=True)
        user_ids = [str(user.id) for user in inactive_users]
        
        updated_count, failed_ids, message = UserService.bulk_update_status(
            user_ids,
            'inactive'
        )
        
        return Response({
            'status': True,
            'message': f"Deactivated {updated_count} inactive users",
            'updated_count': updated_count,
            'failed_ids': failed_ids
        })
    
    @action(detail=False, methods=['get'])
    def export_csv(self, request, *args, **kwargs):
        """
        Export users data as CSV
        """
        # Get all users from the filtered queryset
        queryset = self.get_queryset()
        
        # Create CSV file
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        
        # Write header
        writer.writerow([
            'ID', 'Name', 'Email', 'Role', 'Status', 
            'Registered Date', 'Last Active'
        ])
        
        # Write user data
        for user in queryset:
            status_value = 'pending'
            if user.is_verify and user.is_active:
                status_value = 'approved'
            elif not user.is_active:
                status_value = 'inactive'
                
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if not name:
                name = user.email.split('@')[0]
                
            writer.writerow([
                user.id,
                name,
                user.email,
                user.app_level_role,
                status_value,
                user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                user.updated_at.strftime('%Y-%m-%d %H:%M:%S') if user.updated_at else ''
            ])
        
        # Create response
        response = HttpResponse(csv_buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users.csv"'
        
        return response
    
    


class StudentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Allows tutors to list and retrieve students.
    """
    serializer_class = StudentSerializer
    permission_classes = [permissions.IsAuthenticated]
    # permission_classes = [permissions.IsAuthenticated, IsTutor]

    def get_queryset(self):
        return User.objects.all()
        # return User.objects.filter(app_level_role='student')



from django.db.models import Count

class LessonCompletionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LessonCompletionRateSerializer
    
    def get_queryset(self):
        course_id = self.request.query_params.get('course_id')
        queryset = Lesson.objects.filter(course_id=course_id) if course_id else Lesson.objects.all()
        
        return queryset.annotate(
            total_students=Count('course__user_progress__user', distinct=True),
            completed_students=Count('completed_by__user', distinct=True),
            completion_rate=100.0 * Count('completed_by__user', distinct=True) / 
                           (Count('course__user_progress__user', distinct=True) or 1)
        )
    
    @action(detail=False, methods=['get'])
    def course_summary(self, request):
        """
        Provides an aggregated summary of lesson completion rates by course
        """
        courses = Course.objects.all()
        
        # Get optional date range filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        result = []
        for course in courses:
            # Build query filters
            completion_filter = Q(course=course)
            if start_date:
                completion_filter &= Q(completed_by__completed_at__gte=start_date)
            if end_date:
                completion_filter &= Q(completed_by__completed_at__lte=end_date)
                
            # Count total lessons in course
            total_lessons = course.lessons.count()
            
            # Get total enrolled students
            enrolled_students = UserProgress.objects.filter(course=course).count()
            
            # Calculate completion statistics
            lessons_data = Lesson.objects.filter(course=course).annotate(
                completed_count=Count('completed_by__user', distinct=True, filter=completion_filter),
                completion_percentage=100.0 * Count('completed_by__user', distinct=True, filter=completion_filter) /
                                    (enrolled_students or 1)
            )
            
            # Calculate average completion rate for this course
            avg_completion = lessons_data.aggregate(
                avg_rate=Avg('completion_percentage')
            )['avg_rate'] or 0
            
            # Calculate how many students completed all lessons
            students_completed_all = UserProgress.objects.filter(course=course) \
                .annotate(completed_count=Count('completed_lessons')) \
                .filter(completed_count=total_lessons) \
                .count()
            
            # Course completion rate
            course_completion_rate = 100.0 * students_completed_all / (enrolled_students or 1)
            
            result.append({
                'id': course.id,
                'title': course.title,
                'total_lessons': total_lessons,
                'enrolled_students': enrolled_students,
                'avg_lesson_completion_rate': round(avg_completion, 1),
                'students_completed_all': students_completed_all,
                'course_completion_rate': round(course_completion_rate, 1)
            })
        
        return Response(result)
        
    @action(detail=False, methods=['get'])
    def overall_stats(self, request):
        """
        Provides platform-wide lesson completion statistics
        """
        # Get total lessons, students, and courses
        total_lessons = Lesson.objects.count()
        total_students = get_user_model().objects.filter(progress__isnull=False).distinct().count()
        total_courses = Course.objects.count()
        
        # Overall lesson completion
        total_completions = UserProgress.objects.aggregate(
            total=Count('completed_lessons')
        )['total'] or 0
        
        # Average lessons completed per student
        avg_completions_per_student = total_completions / (total_students or 1)
        
        # Most and least completed lessons
        lesson_stats = Lesson.objects.annotate(
            completion_count=Count('completed_by')
        )
        
        most_completed = lesson_stats.order_by('-completion_count').first()
        least_completed = lesson_stats.order_by('completion_count').first()
        
        # Most engaged course (highest percentage of lesson completions)
        course_engagement = Course.objects.annotate(
            total_lessons=Count('lessons'),
            total_completions=Count('lessons__completed_by'),
            engagement_score=100.0 * Count('lessons__completed_by') / (Count('lessons') * Count('user_progress', distinct=True) or 1)
        ).order_by('-engagement_score')
        
        most_engaging_course = course_engagement.first()
        
        return Response({
            'total_lessons': total_lessons,
            'total_students': total_students,
            'total_courses': total_courses,
            'total_lesson_completions': total_completions,
            'avg_completions_per_student': round(avg_completions_per_student, 1),
            'most_completed_lesson': {
                'id': most_completed.id,
                'title': most_completed.title,
                'course': most_completed.course.title,
                'completion_count': most_completed.completion_count
            } if most_completed else None,
            'least_completed_lesson': {
                'id': least_completed.id,
                'title': least_completed.title,
                'course': least_completed.course.title,
                'completion_count': least_completed.completion_count
            } if least_completed else None,
            'most_engaging_course': {
                'id': most_engaging_course.id,
                'title': most_engaging_course.title,
                'engagement_score': round(most_engaging_course.engagement_score, 1)
            } if most_engaging_course else None
        })
    


