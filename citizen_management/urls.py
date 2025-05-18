from django.urls import path
from. import views
from .views import  RegistrationView, check_username, check_email, logout_view, login_view, \
    ComplaintSubmissionView, get_categories, track_complaint

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', RegistrationView.as_view(), name='register'),
    path('api/check-username/', check_username, name='check_username'),
    path('api/check-email/', check_email, name='check_email'),
    path('logout/', logout_view, name='logout'),
    path('login/', login_view, name='login'),
    path('complaints/new/', ComplaintSubmissionView.as_view(), name='complaint_submission'),
    path('api/agencies/<int:agency_id>/categories/', get_categories, name='get_categories'),
    path('track/', views.track_complaint, name='complaint_tracking'),
    path('citizen_admin', views.citizen_dashboard, name='citizen_admin'),

    path('complaints/', views.complaint_list, name='complaint_list'),
    path('complaints/submit/', views.submit_complaint, name='submit_complaint'),
    path('complaints/<int:pk>/edit/', views.edit_complaint, name='edit_complaint'),
    path('complaints/<str:ticket_number>/', views.complaint_detail, name='complaint_detail'),
    path('complaints/<int:pk>/feedback/', views.submit_feedback, name='submit_feedback'),
    path('complaints/<int:pk>/messages/', views.complaint_messages, name='complaint_messages'),
    path('attachments/<int:pk>/download/', views.download_complaint_attachment, name='download_attachment'),
    # path('notifications/', views.notification_list, name='notification_list'),
    # Notification URLs
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/mark-as-read/<int:notification_id>/', views.mark_notification_as_read,
         name='mark_notification_as_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_read'),
    path('notifications/unread-count/', views.get_unread_count, name='unread_notification_count'),

    # Add these to your existing complaint URLs
    path('complaints/<str:ticket_number>/', views.complaint_detail, name='complaint_detail'),
    path('complaints/<int:pk>/messages/', views.complaint_messages, name='complaint_messages'),
    # ... your other complaint URLs ...

    # Dashboard
    path('agency_admin/', views.AgencyAdminDashboardView.as_view(), name='agency_admin_dashboard'),

    # Complaints
    path('agency_complaints/', views.ComplaintListView.as_view(), name='agency_complaint_list'),
    path('complaints/assigned/', views.AssignedComplaintsView.as_view(), name='agency_assigned_complaints'),
    path('agency_complaints/<str:ticket_number>/', views.ComplaintDetailView.as_view(), name='agency_complaint_detail'),
    path('complaints/<str:ticket_number>/update/', views.UpdateComplaintStatusView.as_view(), name='agency_update_complaint_status'),
    path('complaints/<str:ticket_number>/response/', views.AddResponseView.as_view(), name='agency_add_response'),

    # SLA
    path('sla-violations/', views.SLAViolationsListView.as_view(), name='agency_sla_violations'),

    # Team Management
    path('team/', views.TeamMembersListView.as_view(), name='agency_team_members'),
    path('team/add/', views.TeamMemberCreateView.as_view(), name='agency_team_member_add'),
    path('team/<int:pk>/edit/', views.TeamMemberUpdateView.as_view(), name='agency_team_member_edit'),

    # Service Categories
    path('service-categories/', views.ServiceCategoryListView.as_view(), name='agency_service_categories'),
    path('service-categories/add/', views.ServiceCategoryCreateView.as_view(), name='agency_service_category_add'),
    path('service-categories/<int:pk>/edit/', views.ServiceCategoryUpdateView.as_view(), name='agency_service_category_edit'),

    # Reports
    path('reports/', views.ReportsView.as_view(), name='agency_reports'),

    # Communication
    path('agency_notifications/', views.NotificationsListView.as_view(), name='agency_notifications'),
    path('messages/', views.MessagesListView.as_view(), name='agency_messages'),
    path('messages/send/', views.SendMessageView.as_view(), name='agency_send_message'),

    # Account
    path('profile/', views.ProfileView.as_view(), name='agency_profile'),
    path('settings/', views.AgencySettingsView.as_view(), name='agency_settings'),
]