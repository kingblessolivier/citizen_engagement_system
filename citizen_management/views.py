from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Complaint, StatusUpdate, Response, ComplaintImage
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404, FileResponse
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView
from django.core.paginator import Paginator
from .models import (
    Complaint, ComplaintImage, Response, StatusUpdate,
    Feedback, GovernmentAgency, ServiceCategory
)
from .serializers import ComplaintSerializer, StatusUpdateSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response as DRFResponse
import json

from .forms import ComplaintForm, ComplaintTrackingForm, ComplaintForms
import datetime
from django.contrib.auth.decorators import login_required

from django.db.models import Count, Avg
from .models import ServiceCategory, Complaint, Feedback, GovernmentAgency
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.views.generic import View
from .forms import UserRegistrationForm
from .models import User

from django.contrib import messages


login_required(login_url='/login/')


def home(request):
    # Statistics
    stats = {
        'total_complaints': Complaint.objects.count(),
        'resolved_complaints': Complaint.objects.filter(status='resolved').count(),
        'agencies_count': GovernmentAgency.objects.filter(is_active=True).count(),
        'response_rate': 92,  # This would be calculated based on your business logic
    }

    # Service categories with complaint counts
    service_categories = ServiceCategory.objects.annotate(
        complaint_count=Count('complaints')
    ).filter(is_active=True).order_by('-complaint_count')[:8]

    # Top agencies by resolution rate
    top_agencies = GovernmentAgency.objects.annotate(
        resolved_count=Count('assigned_complaints'),
        feedback_count=Count('assigned_complaints__resolution_feedback'),
        average_rating=Avg('assigned_complaints__resolution_feedback__rating')
    ).filter(is_active=True).order_by('-resolved_count')[:4]

    # Recent testimonials
    testimonials = Feedback.objects.select_related(
        'complaint', 'complaint__category', 'complaint__citizen'
    ).order_by('-submitted_at')[:3]

    # Recent complaints for activity feed
    recent_complaints = Complaint.objects.select_related(
        'category'
    ).order_by('-created_at')[:5]

    # Calculate overall rating
    overall_rating = Feedback.objects.aggregate(
        avg_rating=Avg('rating')
    )['avg_rating'] or 4.5

    context = {
        'stats': stats,
        'service_categories': service_categories,
        'top_agencies': top_agencies,
        'testimonials': testimonials,
        'recent_complaints': recent_complaints,
        'overall_rating': round(overall_rating, 1),
    }

    return render(request, 'home/home.html', context)

class RegistrationView(View):
    template_name = 'user_accounts/register.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, self.template_name)

    def post(self, request):
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return JsonResponse({'success': True, 'redirect_url': '/'})

        errors = {field: [str(error) for error in form.errors[field]] for field in form.errors}
        return JsonResponse({'success': False, 'errors': errors})


def check_username(request):
    username = request.GET.get('username', '')
    exists = User.objects.filter(username__iexact=username).exists()
    return JsonResponse({'exists': exists})


def check_email(request):
    email = request.GET.get('email', '')
    exists = User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'exists': exists})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect(reverse('home'))  # Redirect to your login page


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'redirect_url': '/'  # Change to your desired redirect
                    })
                return redirect('/')

        # Handle errors
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'Invalid username or password'
            })

        # For regular form submission
        return render(request, 'user_accounts/login.html', {'form': form})

    form = AuthenticationForm()
    return render(request, 'user_accounts/login.html', {'form': form})

LoginRequiredMixin.login_url = '/login/'
class ComplaintSubmissionView(LoginRequiredMixin, View):
    template_name = 'complaints/citizen_complaint.html'
    form_class = ComplaintForms

    def get(self, request):
        agencies = GovernmentAgency.objects.filter(is_active=True)
        form = self.form_class(user=request.user)
        return render(request, self.template_name, {
            'agencies': agencies,
            'form': form
        })

    def post(self, request):
        form = self.form_class(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            complaint = form.save(commit=False)

            if not form.cleaned_data['is_anonymous']:
                complaint.citizen = request.user

            if form.cleaned_data['category']:
                complaint.assigned_agency = form.cleaned_data['category'].agency

            complaint.save()

            # Handle multiple image uploads
            for image in request.FILES.getlist('images'):
                ComplaintImage.objects.create(
                    complaint=complaint,
                    image=image,
                    caption=f"Image {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'redirect_url': complaint.get_absolute_url()
                })

            messages.success(request, "Your complaint has been submitted successfully!")
            return redirect(complaint.get_absolute_url())

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data()
            })

        agencies = GovernmentAgency.objects.filter(is_active=True)
        return render(request, self.template_name, {
            'agencies': agencies,
            'form': form
        })


def get_categories(request, agency_id):
    categories = ServiceCategory.objects.filter(
        agency_id=agency_id,
        is_active=True
    ).values('id', 'name')
    return JsonResponse(list(categories), safe=False)


def track_complaint(request):
    if request.method == 'GET' and 'ticket_number' in request.GET:
        ticket_number = request.GET.get('ticket_number')

        try:
            complaint = Complaint.objects.get(ticket_number=ticket_number)

            # Get status updates in chronological order
            updates = list(StatusUpdate.objects.filter(complaint=complaint)
                           .order_by('timestamp')
                           .values('old_status', 'new_status', 'timestamp', 'notes', 'changed_by__username'))

            # Get agency info if assigned
            agency_data = None
            if complaint.assigned_agency:
                agency = complaint.assigned_agency
                agency_data = {
                    'name': agency.name,
                    'short_code': agency.short_code,
                    'contact_phone': agency.contact_phone,
                    'logo': agency.logo.url if agency.logo else None
                }

            data = {
                'success': True,
                'ticket_number': complaint.ticket_number,
                'title': complaint.title,
                'current_status': complaint.status,
                'current_status_display': complaint.get_status_display(),
                'priority': complaint.priority,
                'priority_display': complaint.get_priority_display(),
                'created_at': complaint.created_at.strftime("%Y-%m-%d %H:%M"),
                'category': complaint.category.name if complaint.category else None,
                'agency': agency_data,
                'updates': updates
            }

            return JsonResponse(data)

        except ObjectDoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Complaint not found'
            }, status=404)

    return render(request, 'complaints/tracking.html')


def citizen_admin(request):
    return render(request, 'citizen_dashboard/citizen_base.html')


def citizen_dashboard(request):
    if not request.user.is_authenticated or request.user.role != 'citizen':
        return redirect('login')

    context = {
        'active_complaints': request.user.complaints.exclude(
            status__in=['resolved', 'rejected']
        ).order_by('-updated_at'),
        'resolved_complaints': request.user.complaints.filter(
            status='resolved'
        ).order_by('-updated_at'),
        'pending_feedback': request.user.complaints.filter(
            status='resolved',
            resolution_feedback__isnull=True
        ).order_by('-updated_at'),
        'unread_notifications': request.user.notifications.filter(
            is_read=False
        ).count(),
        'recent_notifications': request.user.notifications.all().order_by('-created_at')[:5],
        'recent_messages': request.user.received_messages.all().order_by('-created_at')[:3],
    }
    return render(request, 'citizen_dashboard/dashboard.html', context)


from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse

from .models import (
    Complaint,
    ServiceCategory,
    Response,
    ComplaintImage,
    StatusUpdate,
    Feedback,
    Notification,
    Message
)
from .forms import (
    ComplaintForm,
    ComplaintImageForm,
    ResponseForm,
    FeedbackForm,
    MessageForm
)


@login_required
def complaint_list(request):
    """
    View for listing and filtering complaints
    """
    # Get all complaints for the current user
    complaints = Complaint.objects.filter(citizen=request.user).order_by('-created_at')

    # Initialize filter variables
    status_choices = Complaint.STATUS_CHOICES
    priority_choices = Complaint.PRIORITY_CHOICES
    categories = ServiceCategory.objects.filter(is_active=True)

    # Get filter parameters from request
    status = request.GET.get('status', '')
    priority = request.GET.get('priority', '')
    category = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')

    # Apply filters
    if status:
        complaints = complaints.filter(status=status)
    if priority:
        complaints = complaints.filter(priority=priority)
    if category:
        complaints = complaints.filter(category_id=category)
    if date_from:
        complaints = complaints.filter(created_at__gte=date_from)
    if date_to:
        complaints = complaints.filter(created_at__lte=date_to)
    if search:
        complaints = complaints.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(ticket_number__icontains=search)
        )

    # Check if any filters are active
    filter_active = any([status, priority, category, date_from, date_to, search])

    # Pagination
    paginator = Paginator(complaints, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'complaints': page_obj,
        'status_choices': status_choices,
        'priority_choices': priority_choices,
        'categories': categories,
        'current_status': status,
        'current_priority': priority,
        'current_category': int(category) if category else None,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search,
        'filter_active': filter_active,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }

    return render(request, 'citizen_dashboard/complaints.html', context)


@login_required
def submit_complaint(request):
    """
    View for submitting a new complaint
    """
    if request.method == 'POST':
        form = ComplaintForm(request.POST, request.FILES)
        image_form = ComplaintImageForm(request.POST, request.FILES)

        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.citizen = request.user
            complaint.citizen_name = request.user.get_full_name()
            complaint.citizen_email = request.user.email
            complaint.save()

            # Handle multiple images
            images = request.FILES.getlist('images')
            for image in images:
                ComplaintImage.objects.create(
                    complaint=complaint,
                    image=image
                )

            # Create initial status update
            StatusUpdate.objects.create(
                complaint=complaint,
                old_status='',
                new_status='submitted',
                changed_by=request.user,
                notes='Complaint submitted by citizen'
            )

            messages.success(request, 'Your complaint has been submitted successfully!')
            return redirect('complaint_detail', ticket_number=complaint.ticket_number)
    else:
        form = ComplaintForm()
        image_form = ComplaintImageForm()

    context = {
        'form': form,
        'image_form': image_form,
        'categories': ServiceCategory.objects.filter(is_active=True)
    }
    return render(request, 'citizen_dashboard/new_complaint.html', context)


@login_required
def edit_complaint(request, pk):
    """
    View for editing an existing complaint
    """
    complaint = get_object_or_404(Complaint, pk=pk, citizen=request.user)

    if complaint.status in ['resolved', 'rejected']:
        messages.warning(request, 'You cannot edit a resolved or rejected complaint.')
        return redirect('complaint_detail', ticket_number=complaint.ticket_number)

    if request.method == 'POST':
        form = ComplaintForm(request.POST, request.FILES, instance=complaint)
        image_form = ComplaintImageForm(request.POST, request.FILES)

        if form.is_valid():
            updated_complaint = form.save()

            # Handle new images
            images = request.FILES.getlist('images')
            for image in images:
                ComplaintImage.objects.create(
                    complaint=updated_complaint,
                    image=image
                )

            messages.success(request, 'Your complaint has been updated successfully!')
            return redirect('complaint_detail', ticket_number=updated_complaint.ticket_number)
    else:
        form = ComplaintForm(instance=complaint)
        image_form = ComplaintImageForm()

    context = {
        'form': form,
        'image_form': image_form,
        'complaint': complaint,
        'categories': ServiceCategory.objects.filter(is_active=True)
    }
    return render(request, 'citizen_dashboard/edit_complaint.html', context)


@login_required
def complaint_detail(request, ticket_number):
    """
    View for displaying complaint details
    """
    complaint = get_object_or_404(
        Complaint,
        ticket_number=ticket_number,
        citizen=request.user
    )

    responses = Response.objects.filter(
        complaint=complaint,
        is_internal=False
    ).order_by('created_at')

    status_updates = StatusUpdate.objects.filter(
        complaint=complaint
    ).order_by('-timestamp')

    images = ComplaintImage.objects.filter(complaint=complaint)

    # Mark notifications as read when viewing complaint
    Notification.objects.filter(
        user=request.user,
        complaint=complaint,
        is_read=False
    ).update(is_read=True)

    # Handle response submission
    if request.method == 'POST' and 'submit_response' in request.POST:
        response_form = ResponseForm(request.POST)
        if response_form.is_valid():
            response = response_form.save(commit=False)
            response.complaint = complaint
            response.author = request.user
            response.save()

            messages.success(request, 'Your response has been submitted!')
            return redirect('complaint_detail', ticket_number=ticket_number)
    else:
        response_form = ResponseForm()

    context = {
        'complaint': complaint,
        'responses': responses,
        'status_updates': status_updates,
        'images': images,
        'response_form': response_form,
        'feedback_form': FeedbackForm() if complaint.status == 'resolved' and not hasattr(complaint,
                                                                                          'resolution_feedback') else None,
    }
    return render(request, 'citizen_dashboard/complaint_details.html', context)


@login_required
def submit_feedback(request, pk):
    """
    View for submitting feedback on a resolved complaint
    """
    complaint = get_object_or_404(
        Complaint,
        pk=pk,
        citizen=request.user,
        status='resolved'
    )

    if hasattr(complaint, 'resolution_feedback'):
        messages.warning(request, 'You have already submitted feedback for this complaint.')
        return redirect('complaint_detail', ticket_number=complaint.ticket_number)

    if request.method == 'POST':
        form = FeedbackForm(request.POST)
        if form.is_valid():
            feedback = form.save(commit=False)
            feedback.complaint = complaint
            feedback.save()

            messages.success(request, 'Thank you for your feedback!')
            return redirect('complaint_detail', ticket_number=complaint.ticket_number)
    else:
        form = FeedbackForm()

    context = {
        'complaint': complaint,
        'form': form
    }
    return render(request, 'citizen_dashboard/submit_feedback.html', context)


@login_required
def complaint_messages(request, pk):
    """
    View for managing messages related to a complaint
    """
    complaint = get_object_or_404(Complaint, pk=pk, citizen=request.user)

    messages_list = Message.objects.filter(
        complaint=complaint
    ).order_by('created_at')

    # Mark messages as read when viewing
    Message.objects.filter(
        complaint=complaint,
        recipient=request.user,
        is_read=False
    ).update(is_read=True)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.complaint = complaint
            message.sender = request.user

            # Determine recipient (agency admin or assigned agent)
            if complaint.assigned_to:
                message.recipient = complaint.assigned_to
            elif complaint.assigned_agency:
                # Get agency admin
                admin = complaint.assigned_agency.user_set.filter(
                    role__in=['agency_admin', 'agent']
                ).first()
                if admin:
                    message.recipient = admin

            message.save()

            # Create notification for recipient
            if message.recipient:
                Notification.objects.create(
                    user=message.recipient,
                    complaint=complaint,
                    notification_type='new_response',
                    message=f'New message from {request.user.get_full_name()} regarding complaint {complaint.ticket_number}'
                )

            messages.success(request, 'Your message has been sent!')
            return redirect('complaint_messages', pk=pk)
    else:
        form = MessageForm()

    context = {
        'complaint': complaint,
        'messages': messages_list,
        'form': form
    }
    return render(request, 'citizen_dashboard/messages.html', context)


@login_required
def download_complaint_attachment(request, pk):
    """
    View for downloading complaint attachments
    """
    image = get_object_or_404(ComplaintImage, pk=pk)
    complaint = image.complaint

    if complaint.citizen != request.user:
        raise Http404("You don't have permission to access this file.")

    response = FileResponse(image.image)
    response['Content-Disposition'] = f'attachment; filename="{image.image.name}"'
    return response


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib import messages

from .models import Notification, Complaint
from .forms import ComplaintFilterForm


@login_required
def notification_list(request):
    """View for listing all notifications for the current user"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')

    # Mark notifications as read when viewing the page
    if request.method == 'GET':
        unread_notifications = notifications.filter(is_read=False)
        unread_notifications.update(is_read=True)

    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'notifications': page_obj,
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count(),
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    return render(request, 'citizen_dashboard/notifications.html', context)


@require_POST
@login_required
def mark_notification_as_read(request, notification_id):
    """Mark a single notification as read (AJAX)"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})


@require_POST
@login_required
def mark_all_notifications_as_read(request):
    """Mark all notifications as read for the current user (AJAX)"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
def get_unread_count(request):
    """Get the count of unread notifications (AJAX)"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})


# Add these to your existing complaint views to create notifications
def create_status_update_notification(complaint, message):
    """Helper function to create status update notifications"""
    Notification.objects.create(
        user=complaint.citizen,
        complaint=complaint,
        notification_type='status_update',
        message=message
    )


def create_response_notification(complaint, responder):
    """Helper function to create response notifications"""
    Notification.objects.create(
        user=complaint.citizen,
        complaint=complaint,
        notification_type='new_response',
        message=f'New response from {responder.get_full_name()} on complaint {complaint.ticket_number}'
    )


def create_assignment_notification(complaint, assignee):
    """Helper function to create assignment notifications"""
    Notification.objects.create(
        user=complaint.citizen,
        complaint=complaint,
        notification_type='assigned',
        message=f'Your complaint {complaint.ticket_number} has been assigned to {assignee.get_full_name()}'
    )


from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q, F, ExpressionWrapper, DurationField, Avg
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.forms.models import model_to_dict

from .models import (
    User, GovernmentAgency, ServiceCategory, Complaint,
    ComplaintImage, Response, StatusUpdate, Feedback,
    Notification, SLAViolation, Message
)
from .forms import (
    UserForm, ServiceCategoryForm, ComplaintStatusForm,
    ResponseForm, AgencyForm, MessageForm
)


class AgencyAdminRequiredMixin(UserPassesTestMixin):
    """Verify that the current user is an agency admin."""

    def test_func(self):
        return self.request.user.role in ['agency_admin', 'super_admin']


class AgencyAdminDashboardView(LoginRequiredMixin, AgencyAdminRequiredMixin, TemplateView):
    template_name = 'agency_admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        agency=GovernmentAgency.objects.get(assigned_user=user)

        # Complaint statistics
        complaints = Complaint.objects.filter(assigned_agency=agency)
        context['total_complaints'] = complaints.count()
        context['open_complaints'] = complaints.exclude(status__in=['resolved', 'rejected']).count()
        context['resolved_complaints'] = complaints.filter(status='resolved').count()
        context['sla_violations'] = complaints.filter(
            sla_deadline__lt=timezone.now(),
            status__in=['submitted', 'acknowledged', 'in_progress']
        ).count()

        # Team statistics
        context['team_members'] = User.objects.filter(
            governmentagency=agency,
            role__in=['agent', 'agency_admin']
        ).count()

        # Recent complaints
        context['recent_complaints'] = complaints.order_by('-created_at')[:5]

        # SLA warnings (complaints nearing deadline)
        warning_threshold = timezone.now() + timedelta(hours=12)
        context['sla_warnings'] = complaints.filter(
            sla_deadline__lte=warning_threshold,
            sla_deadline__gt=timezone.now(),
            status__in=['submitted', 'acknowledged', 'in_progress']
        )[:5]

        return context


class ComplaintListView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = Complaint
    template_name = 'agency_admin/complaint_list.html'
    context_object_name = 'complaints'
    paginate_by = 20

    def get_queryset(self):
        agency = GovernmentAgency.objects.get(assigned_user=self.request.user)
        queryset = Complaint.objects.filter(assigned_agency=agency).order_by('-created_at')

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by priority if provided
        priority = self.request.GET.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        # Filter by category if provided
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(ticket_number__icontains=search) |
                Q(citizen_name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agency = GovernmentAgency.objects.get(assigned_user=self.request.user)
        context['status_choices'] = Complaint.STATUS_CHOICES
        context['priority_choices'] = Complaint.PRIORITY_CHOICES
        context['categories'] = ServiceCategory.objects.filter(agency=agency)
        return context


class AssignedComplaintsView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = Complaint
    template_name = 'agency_admin/assigned_complaints.html'
    context_object_name = 'complaints'
    paginate_by = 20

    def get_queryset(self):
        return Complaint.objects.filter(
            assigned_to=self.request.user,
            assigned_agency=self.request.user.assigned_agency
        ).order_by('-created_at')


class ComplaintDetailView(LoginRequiredMixin, AgencyAdminRequiredMixin, DetailView):
    model = Complaint
    template_name = 'agency_admin/complaint_detail.html'
    context_object_name = 'complaint'
    slug_field = 'ticket_number'
    slug_url_kwarg = 'ticket_number'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        complaint = self.object

        # Add responses
        context['responses'] = Response.objects.filter(complaint=complaint).order_by('created_at')

        # Add status history
        context['status_updates'] = StatusUpdate.objects.filter(complaint=complaint).order_by('-timestamp')

        # Add feedback if exists
        try:
            context['feedback'] = Feedback.objects.get(complaint=complaint)
        except Feedback.DoesNotExist:
            context['feedback'] = None

        # Add SLA information
        if complaint.sla_deadline:
            context['sla_status'] = 'violated' if complaint.sla_deadline < timezone.now() else 'active'
            context['sla_time_remaining'] = complaint.sla_deadline - timezone.now()

        return context


class UpdateComplaintStatusView(LoginRequiredMixin, AgencyAdminRequiredMixin, UpdateView):
    model = Complaint
    form_class = ComplaintStatusForm
    template_name = 'agency_admin/update_complaint_status.html'
    slug_field = 'ticket_number'
    slug_url_kwarg = 'ticket_number'

    def form_valid(self, form):
        old_status = self.object.status
        response = super().form_valid(form)

        # Record status change if it was modified
        if old_status != self.object.status:
            StatusUpdate.objects.create(
                complaint=self.object,
                old_status=old_status,
                new_status=self.object.status,
                changed_by=self.request.user,
                notes=f"Status changed by {self.request.user.get_full_name()}"
            )

            # Create notification for citizen if not anonymous
            if not self.object.is_anonymous and self.object.citizen:
                Notification.objects.create(
                    user=self.object.citizen,
                    complaint=self.object,
                    notification_type='status_change',
                    message=f"Your complaint {self.object.ticket_number} status changed to {self.object.get_status_display()}"
                )

        messages.success(self.request, 'Complaint status updated successfully')
        return response

    def get_success_url(self):
        return reverse('agency_complaint_detail', kwargs={'ticket_number': self.object.ticket_number})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agents'] = User.objects.filter(
            governmentagency=GovernmentAgency.objects.get(assigned_user=self.request.user),
            role='agent'
        )
        return context


class AddResponseView(LoginRequiredMixin, AgencyAdminRequiredMixin, CreateView):
    model = Response
    form_class = ResponseForm
    template_name = 'agency_admin/add_response.html'

    def dispatch(self, request, *args, **kwargs):
        self.complaint = get_object_or_404(
            Complaint,
            ticket_number=self.kwargs['ticket_number']

        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.complaint = self.complaint
        form.instance.author = self.request.user

        # Create notification for citizen if response is not internal
        if not form.instance.is_internal and not self.complaint.is_anonymous and self.complaint.citizen:
            Notification.objects.create(
                user=self.complaint.citizen,
                complaint=self.complaint,
                notification_type='new_response',
                message=f"New response on your complaint {self.complaint.ticket_number}"
            )

        messages.success(self.request, 'Response added successfully')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('agency_complaint_detail', kwargs={'ticket_number': self.complaint.ticket_number})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['complaint'] = self.complaint
        return context


class SLAViolationsListView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = SLAViolation
    template_name = 'agency_admin/sla_violations.html'
    context_object_name = 'violations'
    paginate_by = 20

    def get_queryset(self):
        agency = GovernmentAgency.objects.get(assigned_user=self.request.user)
        return SLAViolation.objects.filter(
            complaint__assigned_agency=agency
        ).order_by('-created_at')


class TeamMembersListView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = User
    template_name = 'agency_admin/team_members.html'
    context_object_name = 'team_members'
    paginate_by = 20

    def get_queryset(self):
        return User.objects.filter(
            governmentagency= GovernmentAgency.objects.get(assigned_user=self.request.user),
            role__in=['agent', 'agency_admin']
        ).order_by('role', 'last_name')


class TeamMemberCreateView(LoginRequiredMixin, AgencyAdminRequiredMixin, CreateView):
    model = User
    form_class = UserForm
    template_name = 'agency_admin/team_member_form.html'
    success_url = reverse_lazy('agency_team_members')

    def form_valid(self, form):
        form.instance.assigned_agency = self.request.user.assigned_agency
        messages.success(self.request, 'Team member added successfully')
        return super().form_valid(form)


class TeamMemberUpdateView(LoginRequiredMixin, AgencyAdminRequiredMixin, UpdateView):
    model = User
    form_class = UserForm
    template_name = 'agency_admin/team_member_form.html'
    success_url = reverse_lazy('agency_team_members')

    def get_queryset(self):
        return User.objects.filter(governmentagency= GovernmentAgency.objects.get(assigned_user=self.request.user))

    def form_valid(self, form):
        messages.success(self.request, 'Team member updated successfully')
        return super().form_valid(form)


class TeamMemberDeactivateView(LoginRequiredMixin, AgencyAdminRequiredMixin, DeleteView):
    model = User
    template_name = 'agency_admin/team_member_confirm_deactivate.html'
    success_url = reverse_lazy('agency_team_members')

    def get_queryset(self):
        return User.objects.filter(
            assigned_agency=self.request.user.assigned_agency
        ).exclude(id=self.request.user.id)

    def form_valid(self, form):
        self.object.is_active = False
        self.object.save()
        messages.success(self.request, 'Team member deactivated successfully')
        return redirect(self.get_success_url())


class ServiceCategoryListView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = ServiceCategory
    template_name = 'agency_admin/service_categories.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return ServiceCategory.objects.filter(
            agency=GovernmentAgency.objects.get(assigned_user=self.request.user),
        ).order_by('name')


class ServiceCategoryCreateView(LoginRequiredMixin, AgencyAdminRequiredMixin, CreateView):
    model = ServiceCategory
    form_class = ServiceCategoryForm
    template_name = 'agency_admin/service_category_form.html'
    success_url = reverse_lazy('agency_service_categories')

    def form_valid(self, form):
        form.instance.agency = GovernmentAgency.objects.get(assigned_user=self.request.user)
        messages.success(self.request, 'Service category added successfully')
        return super().form_valid(form)


class ServiceCategoryUpdateView(LoginRequiredMixin, AgencyAdminRequiredMixin, UpdateView):
    model = ServiceCategory
    form_class = ServiceCategoryForm
    template_name = 'agency_admin/service_category_form.html'
    success_url = reverse_lazy('agency_service_categories')

    def get_queryset(self):
        return ServiceCategory.objects.filter(agency=GovernmentAgency.objects.get(assigned_user=self.request.user))

    def form_valid(self, form):
        messages.success(self.request, 'Service category updated successfully')
        return super().form_valid(form)


class ServiceCategoryDeleteView(LoginRequiredMixin, AgencyAdminRequiredMixin, DeleteView):
    model = ServiceCategory
    template_name = 'agency_admin/service_category_confirm_delete.html'
    success_url = reverse_lazy('agency_service_categories')

    def get_queryset(self):
        return ServiceCategory.objects.filter(agency=self.request.user.assigned_agency)

    def form_valid(self, form):
        messages.success(self.request, 'Service category deleted successfully')
        return super().form_valid(form)


class ReportsView(LoginRequiredMixin, AgencyAdminRequiredMixin, TemplateView):
    template_name = 'agency_admin/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agency = GovernmentAgency.objects.get(assigned_user=self.request.user)

        # Complaint statistics by status
        status_stats = Complaint.objects.filter(
            assigned_agency=agency
        ).values('status').annotate(
            count=Count('id')
        ).order_by('status')

        context['status_stats'] = status_stats

        # Complaint statistics by category
        category_stats = Complaint.objects.filter(
            assigned_agency=agency
        ).values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        context['category_stats'] = category_stats

        # Resolution time statistics
        resolved_complaints = Complaint.objects.filter(
            assigned_agency=agency,
            status='resolved'
        ).annotate(
            resolution_time=ExpressionWrapper(
                F('updated_at') - F('created_at'),
                output_field=DurationField()
            )
        )

        context['avg_resolution_time'] = resolved_complaints.aggregate(
            avg=Avg('resolution_time')
        )['avg']

        # SLA compliance rate
        total_complaints = Complaint.objects.filter(assigned_agency=agency).count()
        sla_violations = SLAViolation.objects.filter(complaint__assigned_agency=agency).count()

        if total_complaints > 0:
            context['sla_compliance_rate'] = 100 - (sla_violations / total_complaints * 100)
        else:
            context['sla_compliance_rate'] = 100

        return context


class NotificationsListView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = Notification
    template_name = 'agency_admin/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        # Mark notifications as read when viewed
        Notification.objects.filter(
            user=self.request.user,
            is_read=False
        ).update(is_read=True)

        queryset = Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')

        # Filter by type if provided
        notification_type = self.request.GET.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        # Filter by read status if provided
        filter_param = self.request.GET.get('filter')
        if filter_param == 'unread':
            queryset = queryset.filter(is_read=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = Notification.objects.filter(
            user=self.request.user,
            is_read=False
        ).count()
        return context


class MarkNotificationReadView(LoginRequiredMixin, AgencyAdminRequiredMixin, UpdateView):
    model = Notification
    fields = []
    http_method_names = ['post']

    def form_valid(self, form):
        form.instance.is_read = True
        form.save()
        return JsonResponse({'status': 'success'})


class MarkAllNotificationsReadView(LoginRequiredMixin, AgencyAdminRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        Notification.objects.filter(
            user=request.user,
            is_read=False
        ).update(is_read=True)
        return JsonResponse({'status': 'success'})


class MessagesListView(LoginRequiredMixin, AgencyAdminRequiredMixin, ListView):
    model = Message
    template_name = 'agency_admin/messages.html'
    context_object_name = 'messages'
    paginate_by = 20

    def get_queryset(self):
        # Mark messages as read when viewed
        Message.objects.filter(
            recipient=self.request.user,
            is_read=False
        ).update(is_read=True)

        queryset = Message.objects.filter(
            Q(sender=self.request.user) | Q(recipient=self.request.user)
        ).order_by('-created_at')

        # Filter by conversation if provided
        conversation_id = self.request.GET.get('conversation')
        if conversation_id:
            other_user = get_object_or_404(User, id=conversation_id)
            queryset = queryset.filter(
                Q(sender=self.request.user, recipient=other_user) |
                Q(sender=other_user, recipient=self.request.user)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all unique conversations
        sent_messages = Message.objects.filter(sender=self.request.user).values('recipient').distinct()
        received_messages = Message.objects.filter(recipient=self.request.user).values('sender').distinct()

        user_ids = set()
        user_ids.update(msg['recipient'] for msg in sent_messages)
        user_ids.update(msg['sender'] for msg in received_messages)

        conversations = []
        for user_id in user_ids:
            user = User.objects.get(id=user_id)
            last_message = Message.objects.filter(
                Q(sender=self.request.user, recipient=user) |
                Q(sender=user, recipient=self.request.user)
            ).latest('created_at')

            unread_count = Message.objects.filter(
                sender=user,
                recipient=self.request.user,
                is_read=False
            ).count()

            conversations.append({
                'other_user': user,
                'last_message': last_message,
                'unread_count': unread_count
            })

        # Sort conversations by last message date
        conversations.sort(key=lambda x: x['last_message'].created_at, reverse=True)
        context['conversations'] = conversations

        # Current conversation details
        conversation_id = self.request.GET.get('conversation')
        if conversation_id:
            context['current_conversation'] = int(conversation_id)
            context['current_recipient'] = User.objects.get(id=conversation_id)

        return context


class SendMessageView(LoginRequiredMixin, AgencyAdminRequiredMixin, CreateView):
    model = Message
    form_class = MessageForm
    template_name = 'agency_admin/send_message.html'
    success_url = reverse_lazy('agency_messages')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        agency = self.request.user.assigned_agency
        form.fields['recipient'].queryset = User.objects.filter(
            assigned_agency=agency
        ).exclude(id=self.request.user.id)
        return form

    def form_valid(self, form):
        form.instance.sender = self.request.user
        complaint_ticket = self.request.GET.get('complaint')
        if complaint_ticket:
            form.instance.complaint = get_object_or_404(Complaint, ticket_number=complaint_ticket)

        # Create notification for recipient
        Notification.objects.create(
            user=form.instance.recipient,
            complaint=form.instance.complaint,
            notification_type='new_message',
            message=f"New message from {self.request.user.get_full_name()}"
        )

        messages.success(self.request, 'Message sent successfully')
        return super().form_valid(form)


class ProfileView(LoginRequiredMixin, AgencyAdminRequiredMixin, UpdateView):
    model = User
    fields = ['first_name', 'last_name', 'email', 'phone', 'profile_picture']
    template_name = 'agency_admin/profile.html'
    success_url = reverse_lazy('agency_profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully')
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        # Handle password change separately
        if 'old_password' in request.POST:
            return self.change_password(request)
        return super().post(request, *args, **kwargs)

    def change_password(self, request):
        user = request.user
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        if not user.check_password(old_password):
            messages.error(request, 'Your current password was entered incorrectly')
            return redirect('agency_profile')

        if new_password1 != new_password2:
            messages.error(request, 'The two password fields didn\'t match')
            return redirect('agency_profile')

        user.set_password(new_password1)
        user.save()
        update_session_auth_hash(request, user)  # Important to keep the user logged in
        messages.success(request, 'Your password was successfully updated!')
        return redirect('agency_profile')


class AgencySettingsView(LoginRequiredMixin, AgencyAdminRequiredMixin, UpdateView):
    model = GovernmentAgency
    form_class = AgencyForm
    template_name = 'agency_admin/agency_settings.html'
    success_url = reverse_lazy('agency_settings')

    def get_object(self):
        return self.request.user.assigned_agency

    def form_valid(self, form):
        messages.success(self.request, 'Agency settings updated successfully')
        return super().form_valid(form)


# API Views for AJAX calls
class ComplaintStatusCountAPIView(LoginRequiredMixin, AgencyAdminRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        agency = request.user.assigned_agency
        status_counts = Complaint.objects.filter(
            assigned_agency=agency
        ).values('status').annotate(
            count=Count('id')
        )

        data = {
            'status_counts': list(status_counts)
        }
        return JsonResponse(data)


class TeamPerformanceAPIView(LoginRequiredMixin, AgencyAdminRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        agency = request.user.assigned_agency
        team_members = User.objects.filter(
            assigned_agency=agency,
            role__in=['agent', 'agency_admin']
        )

        performance_data = []
        for member in team_members:
            assigned_complaints = Complaint.objects.filter(assigned_to=member)
            resolved_complaints = assigned_complaints.filter(status='resolved')

            performance_data.append({
                'name': member.get_full_name(),
                'total_assigned': assigned_complaints.count(),
                'resolved': resolved_complaints.count(),
                'sla_violations': SLAViolation.objects.filter(
                    complaint__in=assigned_complaints
                ).count(),
                'avg_resolution_time': resolved_complaints.annotate(
                    resolution_time=ExpressionWrapper(
                        F('updated_at') - F('created_at'),
                        output_field=DurationField()
                    )
                ).aggregate(
                    avg=Avg('resolution_time')
                )['avg']
            })

        return JsonResponse({'performance_data': performance_data})