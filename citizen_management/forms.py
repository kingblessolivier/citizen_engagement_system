from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from .models import User, Complaint
import re


class UserRegistrationForm(UserCreationForm):
    profile_picture = forms.ImageField(required=False)
    phone = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'role', 'profile_picture', 'password1', 'password2')

    def clean_username(self):
        username = self.cleaned_data['username']
        if not re.match(r'^[a-zA-Z0-9@.+_-]{4,30}$', username):
            raise ValidationError('4-30 characters. Letters, digits and @/./+/-/_ only.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise ValidationError('Email already exists')
        return email

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if phone and not re.match(r'^[0-9]{10,15}$', phone):
            raise ValidationError('Please enter a valid phone number (10-15 digits)')
        return phone

    def clean_profile_picture(self):
        profile_picture = self.cleaned_data.get('profile_picture')
        if profile_picture:
            if profile_picture.size > 2 * 1024 * 1024:  # 2MB
                raise ValidationError('Image size must be less than 2MB')
            if not profile_picture.content_type in ['image/jpeg', 'image/png', 'image/gif']:
                raise ValidationError('Please upload a valid image (JPEG, PNG, GIF)')
        return profile_picture


from django import forms
from django.core.validators import FileExtensionValidator
from .models import Complaint, ComplaintImage, ServiceCategory, GovernmentAgency


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ComplaintForms(forms.ModelForm):
    images = MultipleFileField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif'])],
        help_text="Maximum 5 images (2MB each)"
    )

    class Meta:
        model = Complaint
        fields = [
            'title', 'description', 'category', 'priority', 'source',
            'location_description', 'latitude', 'longitude',
            'citizen_name', 'citizen_email', 'citizen_phone', 'is_anonymous'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'category': forms.Select(attrs={'disabled': True}),
            'latitude': forms.TextInput(attrs={'readonly': True}),
            'longitude': forms.TextInput(attrs={'readonly': True}),
            'is_anonymous': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.is_authenticated:
            self.fields['citizen_name'].initial = user.get_full_name()
            self.fields['citizen_email'].initial = user.email
            self.fields['citizen_phone'].initial = user.phone

        self.fields['citizen_email'].required = not self.initial.get('is_anonymous', False)

    def clean_images(self):
        images = self.files.getlist('images')
        if len(images) > 5:
            raise forms.ValidationError("You can upload a maximum of 5 images.")

        for image in images:
            if image.size > 2 * 1024 * 1024:  # 2MB
                raise forms.ValidationError(f"Image {image.name} is too large (max 2MB each).")
            if not image.content_type.startswith('image/'):
                raise forms.ValidationError(f"File {image.name} is not an image.")

        return images

    def clean(self):
        cleaned_data = super().clean()
        is_anonymous = cleaned_data.get('is_anonymous')
        citizen_email = cleaned_data.get('citizen_email')

        if not is_anonymous and not citizen_email:
            self.add_error('citizen_email', "Email is required when not submitting anonymously.")

        return

class ComplaintTrackingForm(forms.Form):
    ticket_number = forms.CharField(
        label='Complaint Ticket Number',
        max_length=20,
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter your ticket number (e.g., CES-20230515-0001)',
            'autofocus': True
        })
    )


from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (
    Complaint,
    ComplaintImage,
    Response,
    Feedback,
    Message,
    ServiceCategory
)


class ComplaintForm(forms.ModelForm):
    """
    Form for submitting and editing complaints
    """
    category = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.filter(is_active=True),
        label=_("Service Category"),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'data-live-search': 'true'
        }),
        empty_label=_("Select a category")
    )

    location_description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'form-control',
            'placeholder': _('Describe the exact location of the issue')
        }),
        label=_("Location Details")
    )

    class Meta:
        model = Complaint
        fields = [
            'title',
            'category',
            'description',
            'priority',
            'location_description',
            'latitude',
            'longitude',
            'is_anonymous'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Brief summary of your complaint')
            }),
            'description': forms.Textarea(attrs={
                'rows': 5,
                'class': 'form-control',
                'placeholder': _('Please provide detailed information about your complaint')
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'latitude': forms.HiddenInput(),
            'longitude': forms.HiddenInput(),
            'is_anonymous': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'is_anonymous': _('Submit anonymously')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['priority'].choices = [
                                              ('', _('Select priority'))] + list(Complaint.PRIORITY_CHOICES)

        # Set initial category if only one exists
        categories = ServiceCategory.objects.filter(is_active=True)
        if categories.count() == 1:
            self.fields['category'].initial = categories.first()

    def clean(self):
        cleaned_data = super().clean()
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        # Validate location if provided
        if latitude and longitude:
            try:
                lat = float(latitude)
                lng = float(longitude)
                if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                    raise ValidationError(_("Invalid geographic coordinates"))
            except (ValueError, TypeError):
                raise ValidationError(_("Invalid geographic coordinates"))

        return cleaned_data


class ComplaintImageForm(forms.ModelForm):
    """
    Form for uploading complaint images
    """
    images = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'multiple': False,
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label=_("Upload Images")
    )

    class Meta:
        model = ComplaintImage
        fields = ['image']

    def clean_images(self):
        images = self.files.getlist('images')
        if len(images) > 5:
            raise ValidationError(_("You can upload a maximum of 5 images"))

        for image in images:
            if image.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError(_("Image size should not exceed 5MB"))
            if not image.content_type.startswith('image/'):
                raise ValidationError(_("Only image files are allowed"))

        return images


class ResponseForm(forms.ModelForm):
    """
    Form for submitting responses to complaints
    """

    class Meta:
        model = Response
        fields = ['text', 'is_internal']
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': _('Type your response here...')
            }),
            'is_internal': forms.HiddenInput()
        }
        labels = {
            'text': _('Your Response')
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.role == 'citizen':
            self.fields['is_internal'].initial = False
            self.fields['is_internal'].disabled = True


class FeedbackForm(forms.ModelForm):
    """
    Form for submitting feedback on resolved complaints
    """
    RATING_CHOICES = [
        (1, _('⭐ - Very Unsatisfied')),
        (2, _('⭐⭐ - Unsatisfied')),
        (3, _('⭐⭐⭐ - Neutral')),
        (4, _('⭐⭐⭐⭐ - Satisfied')),
        (5, _('⭐⭐⭐⭐⭐ - Very Satisfied')),
    ]

    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'rating-radio'
        }),
        label=_("Your Rating")
    )

    class Meta:
        model = Feedback
        fields = ['rating', 'comments', 'would_recommend']
        widgets = {
            'comments': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': _('Optional: Share more details about your experience')
            }),
            'would_recommend': forms.Select(attrs={
                'class': 'form-control'
            })
        }
        labels = {
            'comments': _('Additional Comments'),
            'would_recommend': _('Would you recommend this service to others?')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['would_recommend'].choices = [
            ('', _('Select an option')),
            (True, _('Yes')),
            (False, _('No')),
            (None, _("I'm not sure"))
        ]


class MessageForm(forms.ModelForm):
    """
    Form for sending messages about complaints
    """

    class Meta:
        model = Message
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': _('Type your message here...')
            })
        }
        labels = {
            'text': _('Message')
        }


class ComplaintFilterForm(forms.Form):
    """
    Form for filtering complaints
    """
    STATUS_CHOICES = [('', _('All Statuses'))] + list(Complaint.STATUS_CHOICES)
    PRIORITY_CHOICES = [('', _('All Priorities'))] + list(Complaint.PRIORITY_CHOICES)

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )

    category = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        empty_label=_('All Categories')
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('From')
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_('To')
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Search complaints...')
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise ValidationError(_("End date cannot be before start date"))

        return cleaned_data


from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from .models import (
    User, GovernmentAgency, ServiceCategory, Complaint,
    Response, Message, Feedback
)


class UserRegistrationForm(UserCreationForm):
    """Form for user registration"""
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, required=True)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'role', 'password1', 'password2'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize form fields as needed
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class UserForm(forms.ModelForm):
    """Form for creating/updating users (used by admin)"""

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'profile_picture', 'is_active'
        ]
        widgets = {
            'role': forms.Select(choices=User.ROLE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        agency = kwargs.pop('agency', None)
        super().__init__(*args, **kwargs)

        # Limit role choices for agency admins
        if agency:
            self.fields['role'].choices = [
                ('citizen', 'Citizen'),
                ('agent', 'Agency Agent'),
                ('agency_admin', 'Agency Administrator'),
            ]


class AgencyForm(forms.ModelForm):
    """Form for government agency creation/update"""

    class Meta:
        model = GovernmentAgency
        fields = [
            'name', 'short_code', 'description',
            'contact_email', 'contact_phone', 'website', 'logo'
        ]


class ServiceCategoryForm(forms.ModelForm):
    """Form for service category creation/update"""

    class Meta:
        model = ServiceCategory
        fields = [
            'name', 'description', 'parent',
            'sla_hours', 'is_active'
        ]
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        agency = kwargs.pop('agency', None)
        super().__init__(*args, **kwargs)

        if agency:
            # Limit parent categories to those belonging to the same agency
            self.fields['parent'].queryset = ServiceCategory.objects.filter(
                agency=agency
            ).exclude(id=self.instance.id)  # Exclude self to prevent circular references


class ComplaintForm(forms.ModelForm):
    """Form for complaint submission"""
    images = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'multiple': False}),
        help_text="Upload multiple images if needed"
    )

    class Meta:
        model = Complaint
        fields = [
            'title', 'description', 'category',
            'location_description', 'latitude', 'longitude',
            'is_anonymous', 'is_public'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'location_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.is_authenticated:
            # Pre-fill citizen info for logged-in users
            self.fields['is_anonymous'].initial = False
            self.fields['is_anonymous'].widget = forms.HiddenInput()

            # Limit categories to active ones
            self.fields['category'].queryset = ServiceCategory.objects.filter(
                is_active=True
            )
        else:
            # For anonymous users, show name/email/phone fields
            self.fields['citizen_name'] = forms.CharField(required=True)
            self.fields['citizen_email'] = forms.EmailField(required=True)
            self.fields['citizen_phone'] = forms.CharField(required=True)


class ComplaintStatusForm(forms.ModelForm):
    """Form for updating complaint status (used by agency staff)"""
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Optional notes about the status change"
    )

    class Meta:
        model = Complaint
        fields = ['status', 'priority', 'assigned_to']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.assigned_agency:
            # Limit assignees to same agency
            self.fields['assigned_to'].queryset = User.objects.filter(
                assigned_agency=user.assigned_agency,
                role='agent'
            )


class ResponseForm(forms.ModelForm):
    """Form for adding responses to complaints"""

    class Meta:
        model = Response
        fields = ['text', 'is_internal']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4}),
            'is_internal': forms.CheckboxInput(),
        }
        labels = {
            'is_internal': 'Mark as internal (visible only to agency staff)'
        }


class FeedbackForm(forms.ModelForm):
    """Form for submitting feedback on resolved complaints"""

    class Meta:
        model = Feedback
        fields = ['rating', 'comments', 'would_recommend']
        widgets = {
            'comments': forms.Textarea(attrs={'rows': 3}),
            'would_recommend': forms.RadioSelect(choices=[(True, 'Yes'), (False, 'No')]),
        }
        labels = {
            'would_recommend': 'Would you recommend our service to others?'
        }


class MessageForm(forms.ModelForm):
    """Form for sending messages between users"""

    class Meta:
        model = Message
        fields = ['recipient', 'text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4}),
            'recipient': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and user.assigned_agency:
            # Limit recipients to same agency
            self.fields['recipient'].queryset = User.objects.filter(
                assigned_agency=user.assigned_agency
            ).exclude(id=user.id)


class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile"""

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email',
            'phone', 'profile_picture'
        ]


class CustomPasswordChangeForm(PasswordChangeForm):
    """Custom password change form with better styling"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})


class ComplaintFilterForm(forms.Form):
    """Form for filtering complaints in the admin dashboard"""
    STATUS_CHOICES = [('', 'All Statuses')] + Complaint.STATUS_CHOICES
    PRIORITY_CHOICES = [('', 'All Priorities')] + Complaint.PRIORITY_CHOICES

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    priority = forms.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    category = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search complaints...'
        })
    )

    def __init__(self, *args, **kwargs):
        agency = kwargs.pop('agency', None)
        super().__init__(*args, **kwargs)

        if agency:
            self.fields['category'].queryset = ServiceCategory.objects.filter(
                agency=agency
            )


class NotificationFilterForm(forms.Form):
    """Form for filtering notifications"""
    TYPE_CHOICES = [
        ('', 'All Types'),
        ('status_change', 'Status Changes'),
        ('new_response', 'New Responses'),
        ('assignment', 'Assignments'),
        ('sla_warning', 'SLA Warnings'),
        ('feedback_request', 'Feedback Requests'),
    ]

    notification_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    filter = forms.ChoiceField(
        choices=[
            ('', 'All Notifications'),
            ('unread', 'Unread Only')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )