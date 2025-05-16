from rest_framework import serializers
from .models import Course, Lesson, Quiz, Question, Option, UserProgress, QuizAttempt, QuizResponse


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']
        # extra_kwargs = {
        #     'is_correct': {'write_only': True}  # Hide correct answers in responses
        # }


class OptionResultSerializer(serializers.ModelSerializer):
    """Serializer that includes the is_correct field for showing quiz results"""
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']


class QuestionSerializer(serializers.ModelSerializer):
    options = OptionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = ['id', 'text', 'options']


class QuestionResultSerializer(serializers.ModelSerializer):
    """Serializer with correct answers for showing quiz results"""
    options = OptionResultSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = ['id', 'text', 'options']


class QuizSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Quiz
        fields = ['id', 'title', 'questions', 'passing_score']


class LessonSerializer(serializers.ModelSerializer):
    quizzes = QuizSerializer(many=True, read_only=True)
    completion_status = serializers.SerializerMethodField()
    
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'order', 'quizzes','completion_status']

    
        
    def get_completion_status(self, lesson):
        """
        Determine lesson completion status:
        - 'completed': User has completed this lesson
        - 'in_progress': This is the user's current lesson
        - 'not_started': User hasn't reached this lesson yet
        - 'locked': This lesson is not available yet (optional)
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 'not_started'
            
        try:
            # Get the user progress for this course
            user_progress = UserProgress.objects.get(
                user=request.user,
                course=lesson.course
            )
            
            # Check if this lesson is in completed lessons
            if lesson in user_progress.completed_lessons.all():
                return 'completed'
                
            # Check if this is the current lesson
            if user_progress.current_lesson == lesson:
                return 'in_progress'
                
            # If this lesson's order is less than current lesson, it should be completed
            # (in case it wasn't properly marked as completed)
            if lesson.order < user_progress.current_lesson.order:
                return 'completed'
                
            # If this lesson's order is greater than current lesson, it's not started yet
            return 'not_started'
            
        except UserProgress.DoesNotExist:
            least_index = min(lesson.course.lessons.all(), key=lambda x: x.id).id
            if lesson.id == least_index:
                return 'in_progress'
            return 'not_started'




class CourseSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = '__all__'

    def get_status(self, course):
        """
        Determine the user's status in the course:
        - 'completed': All lessons in the course are completed
        - 'in_progress': User is currently progressing through one of the lessons
        - 'not_started': User hasn't started the course yet
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 'not_started'
        
        try:
            # Get the user's progress for this course
            user_progress = UserProgress.objects.get(
                user=request.user,
                course=course
            )

            print(user_progress)
            
            # Check if all lessons are completed
            if all(lesson in user_progress.completed_lessons.all() for lesson in course.lessons.all()):
                return 'completed'
            
            # Check if the user is in progress on any lesson
            if user_progress.current_lesson in course.lessons.all():
                return 'in_progress'
            
            # If the user has not started the course, return 'not_started'
            return 'not_started'
        
        except UserProgress.DoesNotExist:
            # If the user has no progress in the course, return 'not_started'
            return 'not_started'



class UserProgressSerializer(serializers.ModelSerializer):
    current_lesson = serializers.PrimaryKeyRelatedField(read_only=True)
    completed_lessons = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:
        model = UserProgress
        fields = ['id', 'user', 'course', 'current_lesson', 'completed_lessons']
        read_only_fields = ['user']


class QuizResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizResponse
        fields = ['question', 'selected_option']
    
    def validate(self, data):
        """Validate that the selected option belongs to the question"""
        question = data['question']
        option = data['selected_option']
        
        if option.question != question:
            raise serializers.ValidationError("The selected option does not belong to this question")
        
        return data


class QuizAttemptSerializer(serializers.ModelSerializer):
    responses = QuizResponseSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'score', 'status', 'attempt_number', 'responses']
        read_only_fields = ['user', 'score', 'status', 'attempt_number']


class QuizAttemptResultSerializer(serializers.ModelSerializer):
    """Detailed serializer for showing quiz results"""
    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'score', 'status', 'attempt_number', 'created_at', 'completed_at']


class QuizSubmitSerializer(serializers.Serializer):
    attempt_id = serializers.IntegerField()
    responses = QuizResponseSerializer(many=True)




from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user list view - basic user information
    """
    name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'app_level_role', 'status', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_name(self, obj):
        """Get full name or formatted email if name not available"""
        name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        if not name:
            # Use part of email if name not provided
            return obj.email.split('@')[0]
        return name
    
    def get_status(self, obj):
        """Determine user status based on flags"""
        if obj.is_verify and obj.is_active:
            return 'approved'
        elif not obj.is_active:
            return 'inactive'
        elif not obj.is_verify:
            return 'pending'
        return 'pending'  # Default fallback

class UserDetailSerializer(serializers.ModelSerializer):
    """
    Serializer for user detail view with all fields
    """
    name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'first_name', 'last_name', 
            'app_level_role', 'status', 'password', 'is_active', 
            'is_verify', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_name(self, obj):
        name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        if not name:
            return obj.email.split('@')[0]
        return name
    
    def get_status(self, obj):
        if obj.is_verify and obj.is_active:
            return 'approved'
        elif not obj.is_active:
            return 'inactive'
        elif not obj.is_verify:
            return 'pending'
        return 'pending'
    
    def validate_password(self, value):
        """
        Validate password using Django's password validators
        """
        if value:
            validate_password(value)
        return value
    
    def update(self, instance, validated_data):
        """
        Handle password hashing on update
        """
        password = validated_data.pop('password', None)
        
        # Update other fields
        instance = super().update(instance, validated_data)
        
        # Handle password update
        if password:
            instance.set_password(password)
            instance.save()
        
        return instance

class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users
    """
    password = serializers.CharField(write_only=True, required=True)
    status = serializers.ChoiceField(
        choices=['approved', 'pending', 'inactive'],
        required=False,
        default='pending'
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name', 
            'app_level_role', 'status'
        ]
    
    def validate_email(self, value):
        """
        Validate that email is unique
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists")
        return value
    
    def validate_password(self, value):
        """
        Validate password using Django's validators
        """
        validate_password(value)
        return value
    
    def validate(self, attrs):
        """
        Convert status to appropriate flag values
        """
        status = attrs.pop('status', 'pending')
        
        # Set flags based on status
        if status == 'approved':
            attrs['is_active'] = True
            attrs['is_verify'] = True
        elif status == 'pending':
            attrs['is_active'] = True
            attrs['is_verify'] = False
        elif status == 'inactive':
            attrs['is_active'] = False
            attrs['is_verify'] = False
        
        return attrs

class UserStatusUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating user status
    """
    status = serializers.ChoiceField(
        choices=['approved', 'pending', 'rejected', 'inactive']
    )

class BulkUserActionSerializer(serializers.Serializer):
    """
    Serializer for bulk user actions
    """
    user_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1
    )
    status = serializers.ChoiceField(
        choices=['approved', 'pending', 'rejected', 'inactive']
    )



class CourseDetailSerializer(serializers.ModelSerializer):
    lessons = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'lessons', 'progress_percentage']
    
    def get_lessons(self, course):
        lessons = course.lessons.all().order('created_at')
        return LessonSerializer(lessons, many=True, context=self.context).data
    
    def get_progress_percentage(self, course):
        """Calculate overall course completion percentage"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return 0
            
        try:
            user_progress = UserProgress.objects.get(
                user=request.user,
                course=course
            )
            
            total_lessons = course.lessons.count()
            if total_lessons == 0:
                return 0
                
            completed_lessons = user_progress.completed_lessons.count()
            return int((completed_lessons / total_lessons) * 100)
            
        except UserProgress.DoesNotExist:
            return 0
        

# class LessonSerializer(serializers.ModelSerializer):
#     completion_status = serializers.SerializerMethodField()
    
#     class Meta:
#         model = Lesson
#         fields = ['id', 'title', 'content', 'order', 'completion_status']
    
#     def get_completion_status(self, lesson):
#         """
#         Determine lesson completion status:
#         - 'completed': User has completed this lesson
#         - 'in_progress': This is the user's current lesson
#         - 'not_started': User hasn't reached this lesson yet
#         - 'locked': This lesson is not available yet (optional)
#         """
#         request = self.context.get('request')
#         if not request or not request.user.is_authenticated:
#             return 'not_started'
            
#         try:
#             # Get the user progress for this course
#             user_progress = UserProgress.objects.get(
#                 user=request.user,
#                 course=lesson.course
#             )
            
#             # Check if this lesson is in completed lessons
#             if lesson in user_progress.completed_lessons.all():
#                 return 'completed'
                
#             # Check if this is the current lesson
#             if user_progress.current_lesson == lesson:
#                 return 'in_progress'
                
#             # If this lesson's order is less than current lesson, it should be completed
#             # (in case it wasn't properly marked as completed)
#             if lesson.order < user_progress.current_lesson.order:
#                 return 'completed'
                
#             # If this lesson's order is greater than current lesson, it's not started yet
#             return 'not_started'
            
#         except UserProgress.DoesNotExist:
#             least_index = min(lesson.course.lessons.all(), key=lambda x: x.id).id
#             if lesson.id == least_index:
#                 return 'in_progress'
#             return 'not_started'


class CourseUploadSerializer(serializers.ModelSerializer):
    pdf_file = serializers.FileField(required=True)

    class Meta:
        model = Course
        fields = ['title', 'description', 'pdf_file']

    def validate_pdf_file(self, value):
        # Optional: Validate the uploaded PDF file (e.g., check file size or type)
        if not value.name.endswith('.pdf'):
            raise serializers.ValidationError("Only PDF files are allowed.")
        return value


class CourseMiniSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = '__all__'  # Or list fields explicitly, e.g., ['id', 'title', 'status', 'completion_percentage']

    def get_status(self, course):
        user = self.context.get('user')
        if not user:
            return 'not_started'
        
        try:
            user_progress = UserProgress.objects.get(user=user, course=course)

            if all(lesson in user_progress.completed_lessons.all() for lesson in course.lessons.all()):
                return 'completed'
            if user_progress.current_lesson in course.lessons.all():
                return 'in_progress'
            return 'not_started'
        
        except UserProgress.DoesNotExist:
            return 'not_started'

    def get_progress(self, course):
        user = self.context.get('user')
        print(user)
        if not user:
            return 0
        
        try:
            user_progress = UserProgress.objects.get(user=user, course=course)
            total_lessons = course.lessons.count()
            print(total_lessons)
            completed_lessons = user_progress.completed_lessons.count()
            print(completed_lessons)

            if total_lessons == 0:
                return 0
            return round((completed_lessons / total_lessons) * 100, 2)

        except UserProgress.DoesNotExist:
            return 0


class StudentSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    class Meta:
        model = User
        # fields = '__all__'
        exclude = ['password', 'is_superuser','groups','user_permissions','app_level_role']

    def get_status(self,obj):
        return 'active' if obj.is_active else 'inactive'
    
    def get_name(self, obj):
        if obj.first_name and obj.last_name:
            return f'{obj.first_name} {obj.last_name}'
        
        return ''

    def get_courses(self,obj):
        
        in_progress_courses = Course.objects.filter(
            user_progress__user=obj,  # Filter using the related UserProgress model
            user_progress__current_lesson__isnull=False  # Ensure current lesson is not null
        )
        
        return CourseMiniSerializer(in_progress_courses,many=True, context={'user':obj}).data

    
class LessonCompletionRateSerializer(serializers.ModelSerializer):
    completion_rate = serializers.FloatField()
    completed_students = serializers.IntegerField()
    total_students = serializers.IntegerField()
    
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'completion_rate', 'completed_students', 'total_students']