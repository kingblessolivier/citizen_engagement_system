
from .models import GovernmentAgency

def agency_info(request):
    if request.user.is_authenticated and hasattr(request.user, 'assigned_agency'):
        return {
            'current_agency': request.user.assigned_agency
        }
    return {}