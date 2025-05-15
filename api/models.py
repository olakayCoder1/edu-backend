from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

# Create your models here.
class Course(models.Model):
    user = models.ForeignKey(get_user_model(), related_name='courses', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Lesson(models.Model):
    course = models.ForeignKey(Course, related_name='lessons', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    content = models.TextField()
    summary = models.TextField(null=True)
    prerequisites = models.JSONField(default=list)
    order = models.PositiveIntegerField(default=1)  # Added to track lesson order
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']  # Order lessons by their position

    def __str__(self):
        return self.title
    

class Quiz(models.Model):
    lesson = models.ForeignKey(Lesson, related_name='quizzes', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    passing_score = models.PositiveIntegerField(default=70, validators=[MinValueValidator(1), MaxValueValidator(100)])  # Added passing score percentage
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(Quiz, related_name='questions', on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.text


class Option(models.Model):
    question = models.ForeignKey(Question, related_name='options', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.text


class UserProgress(models.Model):
    user = models.ForeignKey(get_user_model(), related_name='progress', on_delete=models.CASCADE)
    course = models.ForeignKey(Course, related_name='user_progress', on_delete=models.CASCADE)
    current_lesson = models.ForeignKey(Lesson, related_name='current_users', on_delete=models.CASCADE)
    completed_lessons = models.ManyToManyField(Lesson, related_name='completed_by', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'course']  # One progress record per user per course

    def __str__(self):
        return f"{self.user}'s progress in {self.course.title}"


class QuizAttempt(models.Model):
    STATUS_CHOICES = (
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('passed', 'Passed'),
        ('failed', 'Failed'),
    )
    
    user = models.ForeignKey(get_user_model(), related_name='quiz_attempts', on_delete=models.CASCADE)
    quiz = models.ForeignKey(Quiz, related_name='attempts', on_delete=models.CASCADE)
    score = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    attempt_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'quiz', 'attempt_number']  # Track attempt numbers

    def __str__(self):
        return f"{self.user.username}'s attempt #{self.attempt_number} on {self.quiz.title}"


class QuizResponse(models.Model):
    attempt = models.ForeignKey(QuizAttempt, related_name='responses', on_delete=models.CASCADE)
    question = models.ForeignKey(Question, related_name='responses', on_delete=models.CASCADE)
    selected_option = models.ForeignKey(Option, related_name='selected_in', on_delete=models.CASCADE)
    is_correct = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['attempt', 'question']  # One response per question per attempt

    def __str__(self):
        return f"Response to {self.question.text[:30]}"