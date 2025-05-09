import random, uuid
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractBaseUser , PermissionsMixin ,BaseUserManager
from django.db import models




class UserManager(BaseUserManager):
    """
    Custom manager for the User model.
    """

    def create_user(self,email,password,**extra_fields):
        """
        Create a regular user with the given email and password.
        """
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model( email=email , **extra_fields)
        user.set_password(password)
        user.save()
        return user
    

    def create_superuser(self,email,password, **extra_fields):
        """
        Create a superuser with the given email and password.
        """

        extra_fields.setdefault('is_staff',True)
        extra_fields.setdefault('is_superuser',True)
        extra_fields.setdefault('is_active',True)
        extra_fields.setdefault('is_admin',True)
        extra_fields.setdefault('is_verify',True)
        extra_fields.setdefault('app_level_role','admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('superuser must be given is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('superuser must be given is_superuser=True')
        return self.create_user(email,password,**extra_fields)



class User(AbstractBaseUser, PermissionsMixin):
    APP_LEVEL_ROLE_CHOICES = (
        ("student","Student"),
        ("tutor","Tutor"),
        ("admin","Admin")
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField( max_length=64, null=True,blank=True)
    last_name = models.CharField( max_length=64, null=True,blank=True)
    is_superuser = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    is_verify = models.BooleanField(default=False,null=True,blank=True)
    app_level_role = models.CharField(max_length=12,default='student',choices=APP_LEVEL_ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects= UserManager()
    USERNAME_FIELD = "email"

    def __str__(self):
        return self.email
    

        
