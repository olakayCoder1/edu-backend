from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'courses', views.CourseViewSet, basename='course')
router.register(r'lessons', views.LessonViewSet, basename='lesson')
router.register(r'progress', views.UserProgressViewSet, basename='progress')
router.register(r'quiz-attempts', views.QuizAttemptViewSet, basename='quiz-attempt')
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'students', views.StudentViewSet, basename='student')

urlpatterns = [
    path('courses/upload/', views.CourseUploadView.as_view(), name='course-upload'),
    path('courses/in-progress/', views.InProgressCoursesView.as_view(), name='in-progress-courses'),
    path('courses/<int:course_id>/lessons/<int:lesson_id>/complete/', views.CompleteLessonView.as_view(),  name='complete_lesson'),
    path('', include(router.urls)),
    path('check-lesson-access/<int:lesson_id>/', views.LessonAccessAPIView.as_view(), name='check-lesson-access'),
    path('auth/', include('account.auth_urls')),
]