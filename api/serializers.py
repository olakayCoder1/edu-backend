from rest_framework import serializers
from .models import Course, Lesson, Quiz, Question, Option, UserProgress, QuizAttempt, QuizResponse


class OptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Option
        fields = ['id', 'text', 'is_correct']
        extra_kwargs = {
            'is_correct': {'write_only': True}  # Hide correct answers in responses
        }


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
    
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content', 'order', 'quizzes']


class CourseSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'lessons']


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