
from django.urls import path

from account.views import LoginView, ProfileView, RegisterView,ChangePasswordView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,

)



urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'), # Refresh access token
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),    # Verify token validity
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='ChangePasswordView'),

]