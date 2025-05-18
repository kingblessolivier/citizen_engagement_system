from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import (
    User, GovernmentAgency, ServiceCategory, Complaint,
    ComplaintImage, Response, StatusUpdate, Feedback,
    Notification, SLAViolation, Message
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'profile_picture', 'email_verified',
            'last_login_ip', 'date_joined', 'last_login'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'email_verified': {'read_only': True},
            'last_login_ip': {'read_only': True},
        }

    def create(self, validated_data):
        # Hash password before saving
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Hash password if it's being updated
        if 'password' in validated_data:
            validated_data['password'] = make_password(validated_data['password'])
        return super().update(instance, validated_data)


class GovernmentAgencySerializer(serializers.ModelSerializer):
    class Meta:
        model = GovernmentAgency
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class ServiceCategorySerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)

    class Meta:
        model = ServiceCategory
        fields = '__all__'
        extra_kwargs = {
            'agency': {'required': False},
            'parent': {'required': False},
        }


class ComplaintImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintImage
        fields = ['id', 'image', 'caption', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class ComplaintSerializer(serializers.ModelSerializer):
    images = ComplaintImageSerializer(many=True, read_only=True)
    citizen_details = serializers.SerializerMethodField()
    assigned_to_details = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)
    agency_name = serializers.CharField(source='assigned_agency.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)

    class Meta:
        model = Complaint
        fields = '__all__'
        read_only_fields = [
            'ticket_number', 'created_at', 'updated_at',
            'sla_deadline', 'citizen'
        ]
        extra_kwargs = {
            'citizen_name': {'required': False},
            'citizen_email': {'required': False},
            'citizen_phone': {'required': False},
        }

    def get_citizen_details(self, obj):
        if obj.citizen and not obj.is_anonymous:
            return {
                'name': obj.citizen.get_full_name(),
                'email': obj.citizen.email,
                'phone': obj.citizen.phone
            }
        return None

    def get_assigned_to_details(self, obj):
        if obj.assigned_to:
            return {
                'id': obj.assigned_to.id,
                'name': obj.assigned_to.get_full_name(),
                'email': obj.assigned_to.email
            }
        return None

    def create(self, validated_data):
        # Set citizen to current user if authenticated
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['citizen'] = request.user
            if not validated_data.get('citizen_name'):
                validated_data['citizen_name'] = request.user.get_full_name()
            if not validated_data.get('citizen_email'):
                validated_data['citizen_email'] = request.user.email
            if not validated_data.get('citizen_phone'):
                validated_data['citizen_phone'] = request.user.phone

        return super().create(validated_data)


class ResponseSerializer(serializers.ModelSerializer):
    author_details = serializers.SerializerMethodField()

    class Meta:
        model = Response
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'author']

    def get_author_details(self, obj):
        if obj.author:
            return {
                'id': obj.author.id,
                'name': obj.author.get_full_name(),
                'role': obj.author.role
            }
        return None

    def create(self, validated_data):
        # Set author to current user if authenticated
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['author'] = request.user
        return super().create(validated_data)


class StatusUpdateSerializer(serializers.ModelSerializer):
    changed_by_details = serializers.SerializerMethodField()
    old_status_display = serializers.CharField(source='get_old_status_display', read_only=True)
    new_status_display = serializers.CharField(source='get_new_status_display', read_only=True)

    class Meta:
        model = StatusUpdate
        fields = '__all__'
        read_only_fields = ['timestamp', 'changed_by']

    def get_changed_by_details(self, obj):
        if obj.changed_by:
            return {
                'id': obj.changed_by.id,
                'name': obj.changed_by.get_full_name(),
                'role': obj.changed_by.role
            }
        return None


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = '__all__'
        read_only_fields = ['submitted_at']


class NotificationSerializer(serializers.ModelSerializer):
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    complaint_title = serializers.CharField(source='complaint.title', read_only=True)
    complaint_ticket = serializers.CharField(source='complaint.ticket_number', read_only=True)

    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ['created_at']


class SLAViolationSerializer(serializers.ModelSerializer):
    resolved_by_details = serializers.SerializerMethodField()
    complaint_title = serializers.CharField(source='complaint.title', read_only=True)
    complaint_ticket = serializers.CharField(source='complaint.ticket_number', read_only=True)

    class Meta:
        model = SLAViolation
        fields = '__all__'
        read_only_fields = ['created_at']

    def get_resolved_by_details(self, obj):
        if obj.resolved_by:
            return {
                'id': obj.resolved_by.id,
                'name': obj.resolved_by.get_full_name(),
                'role': obj.resolved_by.role
            }
        return None


class MessageSerializer(serializers.ModelSerializer):
    sender_details = serializers.SerializerMethodField()
    recipient_details = serializers.SerializerMethodField()
    complaint_title = serializers.CharField(source='complaint.title', read_only=True)
    complaint_ticket = serializers.CharField(source='complaint.ticket_number', read_only=True)

    class Meta:
        model = Message
        fields = '__all__'
        read_only_fields = ['created_at', 'sender']

    def get_sender_details(self, obj):
        if obj.sender:
            return {
                'id': obj.sender.id,
                'name': obj.sender.get_full_name(),
                'role': obj.sender.role
            }
        return None

    def get_recipient_details(self, obj):
        if obj.recipient:
            return {
                'id': obj.recipient.id,
                'name': obj.recipient.get_full_name(),
                'role': obj.recipient.role
            }
        return None

    def create(self, validated_data):
        # Set sender to current user if authenticated
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['sender'] = request.user
        return super().create(validated_data)