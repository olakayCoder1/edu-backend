from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from account.models import User
from account.serializers import UserSerializer
from utils.response.response_format import bad_request_response, success_response
from utils.tokens import TokenManager

# Create your views here.
class RegisterView(generics.GenericAPIView):
    serializer_class = UserSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        password = request.data.get('password')
        email = request.data.get('email','').lower()
        role = request.data.get('role')

        if role not in ['student','tutor']:
            return bad_request_response(message='Invalid role')

        if User.objects.filter(email=email).exists():
            return bad_request_response(
                message="Email already exist"
            )
        user = User.objects.create_user(
            password=password, 
            email=email, 
            first_name=first_name,
            last_name=last_name,
            app_level_role=role
        )
        return success_response(
            message='Account created successfully!'
        )


class LoginView(APIView):
    def post(self, request):
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')

        user = authenticate(username=email, password=password)
        if user is not None :
            if user.is_active:
                user:User
                response = {
                    "tokens" : TokenManager.get_tokens_for_user(user) , 
                    'user' : UserSerializer(user).data
                }
                return success_response(data=response)
            else:
                return bad_request_response(message="Your account is disabled, kindly contact the administrative", status_code=401)
            
        return bad_request_response(message='Invalid login credentials')


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=UserSerializer(request.user).data)

    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=serializer.data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=serializer.data)

    def delete(self, request):
        request.user.delete()
        return success_response(status_code=204)
    


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = json.loads(request.body)
        old_password = data.get('current_password')
        new_password = data.get('new_password')

        if not old_password or not new_password:
            return bad_request_response(message="Both old and new passwords are required")

        user = request.user
        if not user.check_password(old_password):
            return bad_request_response(message="Old password is incorrect")

        user.set_password(new_password)
        user.save()
        return success_response(message="Password changed successfully")