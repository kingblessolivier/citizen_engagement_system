from django.contrib import admin
from .models import (
    User,
    GovernmentAgency,
    ServiceCategory,
    Complaint,
    ComplaintImage,
    Response,
    StatusUpdate,
    Feedback,
    Notification,
    SLAViolation,
    Message,
)

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'email_verified')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('role', 'is_active', 'email_verified')

@admin.register(GovernmentAgency)
class GovernmentAgencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code', 'is_active', 'created_at')
    search_fields = ('name', 'short_code')
    list_filter = ('is_active',)

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'agency', 'is_active')
    search_fields = ('name',)
    list_filter = ('agency', 'is_active')

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'title', 'status', 'priority', 'created_at')
    search_fields = ('ticket_number', 'title', 'description', 'citizen_name', 'citizen_email')
    list_filter = ('status', 'priority', 'category', 'assigned_agency')

@admin.register(ComplaintImage)
class ComplaintImageAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'uploaded_at')
    search_fields = ('complaint__ticket_number',)

@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'author', 'created_at')
    search_fields = ('complaint__ticket_number', 'text')
    list_filter = ('is_internal',)

@admin.register(StatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'old_status', 'new_status', 'changed_by', 'timestamp')
    search_fields = ('complaint__ticket_number', 'notes')

@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'rating', 'submitted_at')
    search_fields = ('complaint__ticket_number',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'message')
    list_filter = ('is_read', 'notification_type')

@admin.register(SLAViolation)
class SLAViolationAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'violation_minutes', 'created_at')
    search_fields = ('complaint__ticket_number', 'notes')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('complaint', 'sender', 'recipient', 'created_at')
    search_fields = ('complaint__ticket_number', 'text')
    list_filter = ('is_read',)

# Register your models here