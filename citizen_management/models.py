from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.urls import reverse


class User(AbstractUser):
    """Custom user model with role-based authentication"""
    ROLE_CHOICES = [
        ('citizen', 'Citizen'),
        ('agent', 'Agency Agent'),
        ('agency_admin', 'Agency Administrator'),
        ('super_admin', 'System Administrator'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='citizen')
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True)
    email_verified\
        = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class GovernmentAgency(models.Model):
    """Government agencies that handle complaints"""
    name = models.CharField(max_length=200)
    short_code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='agency_logos/', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_user= models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Government Agencies"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.short_code})"


class ServiceCategory(models.Model):
    """Categories for complaints/feedback"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    agency = models.ForeignKey(
        GovernmentAgency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='categories'
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories'
    )
    sla_hours = models.PositiveIntegerField(
        default=72,
        help_text="Service Level Agreement - hours to respond"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Service Categories"
        ordering = ['agency__name', 'name']

    def __str__(self):
        return f"{self.agency.short_code if self.agency else 'System'}: {self.name}"


class Complaint(models.Model):
    """Main complaint/feedback submission model"""
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
        ('reopened', 'Reopened'),
    ]

    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    SOURCE_CHOICES = [
        ('web', 'Website'),
        ('mobile', 'Mobile App'),
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('office', 'Field Office'),
    ]

    # Core fields
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.SET_NULL,
        null=True,
        related_name='complaints'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='submitted'
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium'
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='web'
    )

    # Location information
    location_description = models.TextField(blank=True)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )

    # Citizen information
    citizen = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints'
    )
    citizen_name = models.CharField(max_length=100, blank=True)
    citizen_email = models.EmailField(blank=True)
    citizen_phone = models.CharField(max_length=20, blank=True)
    is_anonymous = models.BooleanField(default=False)

    # Assignment and tracking
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_complaints'
    )
    assigned_agency = models.ForeignKey(
        GovernmentAgency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_complaints'
    )
    sla_deadline = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['priority']),
            models.Index(fields=['category']),
            models.Index(fields=['assigned_agency']),
        ]

    def __str__(self):
        return f"{self.ticket_number}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            self.ticket_number = self.generate_ticket_number()
        if self.category and not self.sla_deadline:
            self.sla_deadline = timezone.now() + timezone.timedelta(
                hours=self.category.sla_hours
            )
        super().save(*args, **kwargs)

    def generate_ticket_number(self):
        date_str = timezone.now().strftime("%Y%m%d")
        last_complaint = Complaint.objects.filter(
            ticket_number__startswith=f"CES-{date_str}"
        ).order_by('-ticket_number').first()

        if last_complaint:
            last_num = int(last_complaint.ticket_number[-4:])
            new_num = last_num + 1
        else:
            new_num = 1

        return f"CES-{date_str}-{new_num:04d}"

    def get_absolute_url(self):
        return reverse('complaint_detail', kwargs={'ticket_number': self.ticket_number})


class ComplaintImage(models.Model):
    """Images attached to complaints"""
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='complaints/images/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.complaint.ticket_number}"


class Response(models.Model):
    """Responses to complaints from agencies or citizens"""
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    text = models.TextField()
    is_internal = models.BooleanField(
        default=False,
        help_text="Visible only to agency staff"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Response to {self.complaint.ticket_number}"


class StatusUpdate(models.Model):
    """History of status changes for complaints"""
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='status_updates'
    )
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return (f"{self.complaint.ticket_number} changed from "
                f"{self.old_status} to {self.new_status}")


class Feedback(models.Model):
    """Citizen feedback on complaint resolution"""
    complaint = models.OneToOneField(
        Complaint,
        on_delete=models.CASCADE,
        related_name='resolution_feedback'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1 (Very Unsatisfied) to 5 (Very Satisfied)"
    )
    comments = models.TextField(blank=True)
    would_recommend = models.BooleanField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback ({self.rating}/5) for {self.complaint.ticket_number}"


class Notification(models.Model):
    """System notifications for users"""
    TYPE_CHOICES = [
        ('status_change', 'Status Change'),
        ('new_response', 'New Response'),
        ('assignment', 'New Assignment'),
        ('sla_warning', 'SLA Warning'),
        ('feedback_request', 'Feedback Request'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_read']),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} notification for {self.user}"


class SLAViolation(models.Model):
    """Track violations of Service Level Agreements"""
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='sla_violations'
    )
    expected_resolution_time = models.DateTimeField()
    actual_resolution_time = models.DateTimeField()
    violation_minutes = models.PositiveIntegerField()
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SLA Violation for {self.complaint.ticket_number}"


class Message(models.Model):
    """Internal messages between agency staff and citizens"""
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_messages'
    )
    recipient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_messages'
    )
    text = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender} to {self.recipient} for {self.complaint.ticket_number}"
