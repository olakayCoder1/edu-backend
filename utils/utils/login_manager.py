from django.utils import timezone
from datetime import timedelta
from account.models import LoginActivity


class LoginManager:

    @staticmethod
    def log_user_login(request, user, **kwargs):
        # Get the current date
        today = timezone.now().date()

        # Check if there's already a login record for today
        existing_record = LoginActivity.objects.filter(user=user, created_at__date=today).first()

        if not existing_record:
            # No record exists for today, so create a new one
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT')
            LoginActivity.objects.create(user=user, ip_address=ip_address, user_agent=user_agent)



    @staticmethod
    def determine_logging_behavior(user):
        # Define the time period for analysis
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Count user logins in the last 30 days
        login_count = LoginActivity.objects.filter(user=user, created_at__gte=thirty_days_ago).count()
        
        # Categorize the login behavior
        if login_count >= 25:  # Approximately daily
            return "Daily"
        elif 8 <= login_count < 25:  # Multiple times a week
            return "Weekly"
        elif 1 <= login_count < 8:  # At least once a month
            return "Monthly"
        else:  # Very infrequent
            return "Not Often"
