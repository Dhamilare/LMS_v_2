from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import *


# --- Custom Authentication Forms ---

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['username'].widget.attrs.update({
            'class': 'block w-full p-3 border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition',
            'placeholder': 'Username'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'block w-full p-3 border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition',
            'placeholder': 'Password'
        })


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'block w-full p-3 border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition',
                'placeholder': field.label
            })

class UserForm(forms.ModelForm):
    """
    A form for editing existing user details.
    """
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-4 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500'}),
            'role': forms.Select(attrs={'class': 'w-full px-4 py-2 border rounded-md focus:ring-blue-500 focus:border-blue-500'}),
        }


class AdminUserCreationForm(UserCreationForm):
    """
    A custom form for administrators to create a new user.
    It includes fields for username, email, password, and the user's role.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.help_text = ''
            field.widget.attrs.update({
                'class': 'block w-full p-3 border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition',
                'placeholder': field.label
            })


# --- Instructor-specific Forms ---

class CourseForm(forms.ModelForm):
    """Form to create or edit a course."""
    class Meta:
        model = Course
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Course Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Course Description'}),
        }


class LessonForm(forms.ModelForm):
    """Form to create a new lesson."""
    class Meta:
        model = Lesson
        fields = ['title', 'content', 'video_url', 'resource_file', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Lesson Title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Lesson content (supports Markdown)'}),
            'video_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'YouTube or Vimeo URL'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class AssignmentForm(forms.ModelForm):
    """Form to create a new assignment."""
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assignment Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Assignment Description'}),
            # We'll use a datepicker widget in the template for a rich UX
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

class QuizForm(forms.ModelForm):
    """Form to create a new quiz."""
    class Meta:
        model = Quiz
        fields = ['title', 'passing_score']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Quiz Title'}),
            'passing_score': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class QuestionForm(forms.ModelForm):
    """Form to create a new question for a quiz."""
    class Meta:
        model = Question
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Question text'}),
        }

class ChoiceForm(forms.ModelForm):
    """Form to create choices for a question."""
    class Meta:
        model = Choice
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choice text'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# --- Student-specific Forms ---

class SubmissionForm(forms.ModelForm):
    """Form for students to submit an assignment file."""
    class Meta:
        model = Submission
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }

class SupportTicketForm(forms.ModelForm):
    """Form for users to create a support ticket."""
    class Meta:
        model = SupportTicket
        fields = ['subject', 'description']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject of your issue'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Describe your issue in detail'}),
        }

class StudentProgressForm(forms.ModelForm):
    """
    A form for creating or updating StudentProgress entries.
    """
    class Meta:
        model = StudentProgress
        fields = ['student', 'lesson', 'is_completed']