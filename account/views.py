from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.
class RegisterView(View):
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

@method_decorator(csrf_exempt, name='dispatch') 
class LoginView(View):
    def post(self, request):
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'message': 'Login successful'}, status=200)
        else:
            return JsonResponse({'error': 'Invalid credentials'}, status=400)

class ProfileView(LoginRequiredMixin, View):
    def get(self, request):
        return JsonResponse({
            'username': request.user.username,
            'email': request.user.email
        }, status=200)

    def put(self, request):
        data = json.loads(request.body)
        email = data.get('email')
        if email:
            request.user.email = email
            request.user.save()
            return JsonResponse({'message': 'Profile updated successfully'}, status=200)
        else:
            return JsonResponse({'error': 'Email is required'}, status=400)
