from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from account.models import User
from account.serializers import UserSerializer
from utils.response.response_format import bad_request_response, success_response
from utils.tokens import TokenManager

# Create your views here.
class RegisterView(APIView):
    def post(self, request):
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email')
        if not username or not password or not email:
            return JsonResponse({'error': 'Missing fields'}, status=400)
        if User.objects.filter(username=username).exists():
            return JsonResponse({'error': 'Username already exists'}, status=400)
        user = User.objects.create_user(username=username, password=password, email=email)
        return JsonResponse({'message': 'User registered successfully'}, status=201)


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
        return success_response(
            data=UserSerializer(request.user).data
        )

    def put(self, request):
        data = json.loads(request.body)
        email = data.get('email')
        if email:
            request.user.email = email
            request.user.save()
            return JsonResponse({'message': 'Profile updated successfully'}, status=200)
        else:
            return JsonResponse({'error': 'Email is required'}, status=400)
