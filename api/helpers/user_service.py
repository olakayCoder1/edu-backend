import uuid
from typing import Dict, List, Optional, Tuple, Any

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

class UserService:
    """
    Service class for user management operations
    """
    
    @staticmethod
    def get_all_users(filters: Optional[Dict] = None, search_term: Optional[str] = None) -> List[User]:
        """
        Get all users with optional filtering and search
        
        Args:
            filters: Dictionary of filter parameters
            search_term: Search string for name or email
            
        Returns:
            List of user objects
        """
        queryset = User.objects.all()
        
        # Apply filters if provided
        if filters:
            # Role filter
            if 'role' in filters and filters['role'] != 'all':
                queryset = queryset.filter(app_level_role=filters['role'])
                
            # Status filter
            if 'status' in filters:
                status = filters['status']
                if status == 'approved':
                    queryset = queryset.filter(is_active=True, is_verify=True)
                elif status == 'pending':
                    queryset = queryset.filter(is_verify=False)
                elif status == 'inactive':
                    queryset = queryset.filter(is_active=False)
                    
            # Date range filter
            if 'date_from' in filters and 'date_to' in filters:
                queryset = queryset.filter(created_at__range=[filters['date_from'], filters['date_to']])
        
        # Apply search term if provided
        if search_term:
            queryset = queryset.filter(
                Q(email__icontains=search_term) |
                Q(first_name__icontains=search_term) |
                Q(last_name__icontains=search_term)
            )
            
        return queryset
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[User]:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            User object if found, None otherwise
        """
        try:
            return User.objects.get(id=uuid.UUID(user_id))
        except (User.DoesNotExist, ValueError):
            return None
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """
        Get user by email
        
        Args:
            email: User email
            
        Returns:
            User object if found, None otherwise
        """
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None
    
    @staticmethod
    @transaction.atomic
    def create_user(user_data: Dict[str, Any]) -> Tuple[User, bool, str]:
        """
        Create a new user
        
        Args:
            user_data: Dictionary containing user data
            
        Returns:
            Tuple of (user object, success boolean, message string)
        """
        # Extract required fields
        email = user_data.get('email')
        password = user_data.get('password')
        app_level_role = user_data.get('app_level_role', 'student')
        
        # Validate email
        if not email:
            return None, False, "Email is required"
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return None, False, "User with this email already exists"
        
        # Create user
        try:
            user = User(
                email=email,
                app_level_role=app_level_role,
                first_name=user_data.get('first_name', ''),
                last_name=user_data.get('last_name', ''),
                is_active=user_data.get('is_active', True),
                is_verify=user_data.get('is_verify', False)
            )
            
            if password:
                user.set_password(password)
                
            user.save()
            return user, True, "User created successfully"
        
        except ValidationError as e:
            return None, False, str(e)
        except Exception as e:
            return None, False, f"Error creating user: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def update_user(user_id: str, update_data: Dict[str, Any]) -> Tuple[Optional[User], bool, str]:
        """
        Update user data
        
        Args:
            user_id: User ID
            update_data: Dictionary containing fields to update
            
        Returns:
            Tuple of (updated user object, success boolean, message string)
        """
        user = UserService.get_user_by_id(user_id)
        if not user:
            return None, False, "User not found"
        
        try:
            # Update basic fields
            if 'first_name' in update_data:
                user.first_name = update_data['first_name']
                
            if 'last_name' in update_data:
                user.last_name = update_data['last_name']
                
            if 'app_level_role' in update_data:
                user.app_level_role = update_data['app_level_role']
                
            # Handle status changes
            if 'status' in update_data:
                status = update_data['status']
                if status == 'approved':
                    user.is_active = True
                    user.is_verify = True
                elif status == 'pending':
                    user.is_verify = False
                elif status == 'rejected':
                    user.is_active = False
                elif status == 'inactive':
                    user.is_active = False
            
            # Handle explicit boolean flags
            if 'is_active' in update_data:
                user.is_active = update_data['is_active']
                
            if 'is_verify' in update_data:
                user.is_verify = update_data['is_verify']
                
            # Handle password update if provided
            if 'password' in update_data and update_data['password']:
                user.set_password(update_data['password'])
            
            user.save()
            return user, True, "User updated successfully"
        
        except Exception as e:
            return None, False, f"Error updating user: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def delete_user(user_id: str) -> Tuple[bool, str]:
        """
        Delete a user
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (success boolean, message string)
        """
        user = UserService.get_user_by_id(user_id)
        if not user:
            return False, "User not found"
        
        try:
            user.delete()
            return True, "User deleted successfully"
        except Exception as e:
            return False, f"Error deleting user: {str(e)}"
    
    @staticmethod
    @transaction.atomic
    def bulk_update_status(user_ids: List[str], status: str) -> Tuple[int, List[str], str]:
        """
        Update status for multiple users
        
        Args:
            user_ids: List of user IDs
            status: New status ('approved', 'pending', 'inactive')
            
        Returns:
            Tuple of (count of updated users, list of failed IDs, message string)
        """
        updated_count = 0
        failed_ids = []
        
        for user_id in user_ids:
            user = UserService.get_user_by_id(user_id)
            if not user:
                failed_ids.append(user_id)
                continue
                
            try:
                if status == 'approved':
                    user.is_active = True
                    user.is_verify = True
                elif status == 'pending':
                    user.is_verify = False
                elif status == 'inactive' or status == 'rejected':
                    user.is_active = False
                    
                user.save()
                updated_count += 1
                
            except Exception:
                failed_ids.append(user_id)
        
        return updated_count, failed_ids, f"Updated {updated_count} users"
    
    @staticmethod
    def get_user_stats() -> Dict[str, int]:
        """
        Get user statistics
        
        Returns:
            Dictionary of user statistics
        """
        all_users = User.objects.all()
        
        # Calculate counts
        total_users = all_users.count()
        active_students = all_users.filter(app_level_role='student', is_active=True, is_verify=True).count()
        active_tutors = all_users.filter(app_level_role='tutor', is_active=True, is_verify=True).count()
        pending_approvals = all_users.filter(is_verify=False).count()
        pending_students = all_users.filter(app_level_role='student', is_verify=False).count()
        pending_tutors = all_users.filter(app_level_role='tutor', is_verify=False).count()
        
        return {
            'total_users': total_users,
            'active_students': active_students,
            'active_tutors': active_tutors,
            'pending_approvals': pending_approvals,
            'pending_students': pending_students,
            'pending_tutors': pending_tutors
        }
    
    @staticmethod
    def format_user_for_frontend(user: User) -> Dict[str, Any]:
        """
        Format user data for frontend response
        
        Args:
            user: User object
            
        Returns:
            Dictionary of formatted user data
        """
        # Calculate status based on is_active and is_verify flags
        status = 'pending'
        if user.is_verify and user.is_active:
            status = 'approved'
        elif not user.is_active:
            status = 'inactive'
        elif not user.is_verify:
            status = 'pending'
            
        name = f"{user.first_name or ''} {user.last_name or ''}".strip()
        if not name:
            name = user.email.split('@')[0]
            
        return {
            'id': str(user.id),
            'name': name,
            'email': user.email,
            'role': user.app_level_role,
            'status': status,
            'registeredAt': user.created_at.isoformat(),
            'lastActive': user.updated_at.isoformat() if user.updated_at else None
        }