# Complaint Management System - README

## Overview

This system provides a comprehensive platform for citizens to submit complaints to government agencies and track their resolution progress. It includes three main user roles:

1. **Citizens** - Can submit, track, and receive updates on complaints
2. **Agency Admins** - Manage complaint resolution processes and teams
3. **Agency Agents** - Handle assigned complaints and communicate with citizens

## here are usernames and passwords to use.
-**citizen dashboard:**
-username: mugabo   password: Olivier@12
-**agency dashboard:**
-username: olivier   password: Olivier@12
-**Admin dashboard:**
-username: admin   password: Olivier@12




## Key Features

### For Citizens
- **User Registration & Authentication**
  - Secure account creation with email/username validation
  - Login/logout functionality
  - Profile management
  - username: mugabo
  - password: Olivier@12

- **Complaint Management**
  - Submit new complaints with multiple attachments
  - Track complaint status in real-time
  - View complaint history and responses
  - Submit feedback on resolved complaints

- **Communication**
  - Exchange messages with agency staff
  - Receive notifications about status changes
  - Get response alerts

### For Agency Staff (Admins & Agents)
- **Dashboard**

  
  - Overview of complaint statistics
  - SLA violation alerts
  - Recent activity feed

- **Complaint Processing**
  - View and filter complaints by status/priority/category
  - Update complaint status with audit trail
  - Assign complaints to agents
  - Add responses (internal or public)

- **Team Management**
  - Add/edit team members
  - Assign roles and permissions
  - Track agent performance metrics

- **Reporting**
  - Complaint resolution analytics
  - SLA compliance rates
  - Category-wise performance

## System Architecture

### Core Models
1. **User** - All system users with role-based permissions
2. **Complaint** - Central entity with status tracking
3. **GovernmentAgency** - Departments handling complaints
4. **ServiceCategory** - Complaint classification system
5. **StatusUpdate** - Audit trail for complaint state changes
6. **Response** - Communications about complaints
7. **Feedback** - Citizen ratings of resolution quality

### Workflow

1. **Submission**
   - Citizen submits complaint via form
   - System generates ticket number
   - Complaint assigned to appropriate agency/category

2. **Processing**
   - Agency admin assigns to agent
   - Status updates trigger notifications
   - Internal/external communications logged

3. **Resolution**
   - Final status set (resolved/rejected)
   - Citizen provides feedback
   - Case closed with performance metrics recorded

## API Endpoints

### Citizen Facing
- `/api/complaints/` - Submit/list complaints
- `/api/track/<ticket_number>` - Check complaint status
- `/api/categories/<agency_id>` - Get service categories

### Admin Facing
- `/api/status_counts/` - Complaint statistics by status
- `/api/team_performance/` - Agent productivity metrics
- `/api/sla_violations/` - List of overdue complaints

## Installation & Setup

1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure database settings
4. Run migrations: `python manage.py migrate`
5. Create superuser: `python manage.py createsuperuser`
6. Start development server: `python manage.py runserver`

## Security Features

- Role-based access control
- Password hashing
- CSRF protection
- Session authentication
- Input validation
- Audit trails for status changes

## Customization Points

1. **SLA Rules** - Modify in `models.py`
2. **Notification Templates** - Update message formats
3. **Dashboard Widgets** - Add/remove metrics
4. **Report Formats** - Customize analytics views

## Dependencies

- Django 3.2+
- Python 3.8+
- PostgreSQL/MySQL (recommended for production)
- Pillow (image processing)

## Deployment Notes

For production environments:
- Use WSGI server (Gunicorn/uWSGI)
- Configure static files properly
- Set up email backend
- Enable proper HTTPS configuration
- Implement regular backups

This system provides government agencies with a transparent, accountable platform for addressing citizen concerns while giving citizens visibility into the resolution process.
