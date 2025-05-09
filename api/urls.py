from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'lessons', views.LessonViewSet, basename='lesson')
router.register(r'progress', views.UserProgressViewSet, basename='progress')
router.register(r'quiz-attempts', views.QuizAttemptViewSet, basename='quiz-attempt')

urlpatterns = [
    path('', include(router.urls)),
    path('check-lesson-access/<int:lesson_id>/', views.LessonAccessAPIView.as_view(), name='check-lesson-access'),
    path('auth/', include('account.auth_urls')),
]