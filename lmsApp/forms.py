# core/forms.py (Instructor is_staff=False Corrected)
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, HTML, Row, Column
from .models import *
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import authenticate
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.hashers import make_password


class SetPasswordModelForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full border border-gray-300 px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Enter password'
        })
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'block w-full border border-gray-300 px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Confirm password'
        })
    )

    class Meta:
        model = User
        fields = []

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.password = make_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class SetPasswordForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Enter password", "class": "form-control"})
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password", "class": "form-control"})
    )

    class Meta:
        model = User
        fields = []  # no direct model fields because we'll handle password manually

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data["password1"]
        user.set_password(password)
        if commit:
            user.save()
        return user

class CustomSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the help text from both password fields
        self.fields['new_password1'].help_text = ''
        self.fields['new_password2'].help_text = ''


class StudentRegistrationForm(forms.ModelForm):
    """
    Custom form for student registration.
    """

    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}),
        help_text=""
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm your password"}),
        help_text=""
    )

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name")
        widgets = {
            "username": forms.TextInput(attrs={"placeholder": "Choose a username"}),
            "email": forms.EmailInput(attrs={"placeholder": "Enter your email address"}),
            "first_name": forms.TextInput(attrs={"placeholder": "Your first name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Your last name"}),
        }
        help_texts = {field: "" for field in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Tailwind styles
        base_classes = (
            "w-full block bg-white border border-gray-300 rounded-md "
            "px-4 py-3 text-gray-800 placeholder-gray-500 "
            "focus:border-blue-500 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
        )
        error_classes = (
            "w-full block bg-white border border-red-500 rounded-md "
            "px-4 py-3 text-gray-800 placeholder-gray-500 "
            "focus:border-red-500 focus:ring focus:ring-red-200 focus:ring-opacity-50"
        )

        # Apply dynamic styles
        for field_name, field in self.fields.items():
            css_classes = error_classes if self.errors.get(field_name) else base_classes
            field.widget.attrs.update({"class": css_classes})

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_password2(self):
        password = self.cleaned_data.get("password")
        password2 = self.cleaned_data.get("password2")

        if password and password2 and password != password2:
            raise ValidationError("Passwords do not match.")

        try:
            validate_password(password, self.instance)
        except ValidationError as e:
            self.add_error("password", e)
            raise

        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_student = True
        user.is_instructor = False
        user.is_staff = False
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """
    Custom form for user login, allowing login with email instead of username,
    and providing more specific error messages for email/password validation.
    """
    # Overriding the username field to change its label and to handle email input
    username = forms.CharField(
        label="Email",
        widget=forms.TextInput(attrs={'autofocus': True}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Base Tailwind block style
        base_classes = (
            "w-full block bg-white border border-gray-300 rounded-md "
            "px-4 py-3 text-gray-800 placeholder-gray-500 "
            "focus:border-blue-500 focus:ring focus:ring-blue-200 focus:ring-opacity-50"
        )
        error_classes = (
            "w-full block bg-white border border-red-500 rounded-md "
            "px-4 py-3 text-gray-800 placeholder-gray-500 "
            "focus:border-red-500 focus:ring focus:ring-red-200 focus:ring-opacity-50"
        )

        # Apply block style dynamically
        for field_name, field in self.fields.items():
            css_classes = error_classes if self.errors.get(field_name) else base_classes
            placeholder = f"Enter your {field.label.lower()}"
            field.widget.attrs.update({"class": css_classes, "placeholder": placeholder})
            
    def clean(self):
        """
        Overrides the clean method to provide specific errors for email and password.
        """
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if not email:
            raise ValidationError("Email is required.")
        if not password:
            raise ValidationError("Password is required.")

        try:
            # First, try to find a user with the provided email.
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            # If no user is found with that email, raise a specific error on the username field.
            raise ValidationError(
                "No account is registered with that email address.",
                code="invalid_email",
                params={'field': 'username'}
            )
        else:
            # If a user is found, attempt to authenticate with the found user's username.
            authenticated_user = authenticate(self.request, username=user.username, password=password)
            if authenticated_user is None:
                # If authentication fails, it's because the password was wrong.
                raise ValidationError(
                    "Incorrect password.",
                    code="invalid_password",
                    params={'field': 'password'}
                )
            
            # If all checks pass, set the user on the form and pass it along.
            self.user_cache = authenticated_user

        return self.cleaned_data
    


class InstructorCreationForm(UserCreationForm):
    """
    Form for Admin to create Instructor accounts.
    """
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('username', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('email', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('first_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('last_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('password', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('password2', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Create Instructor', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_instructor = True # Set new user as instructor
        user.is_student = False # Ensure they are not students
        user.is_staff = False # Corrected: Instructors are NOT staff/admin
        if commit:
            user.save()
        return user
    
class InstructorUpdateForm(UserChangeForm):
    """
    Form for Admin to update Instructor accounts.
    Excludes password fields for security, as password changes should be separate.
    """
    password = None # Exclude password field from this form

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
        # Remove help_texts for all fields if desired, similar to StudentRegistrationForm
        help_texts = {f: '' for f in fields} # Set all help_texts to empty string

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('username', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('email', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('first_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('last_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Update Instructor', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'instructor', 'price', 'is_published', 'thumbnail']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'thumbnail': forms.URLInput(attrs={'placeholder': 'e.g., https://example.com/course_thumb.jpg'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['instructor'].queryset = User.objects.filter(is_instructor=True).order_by('username')


class ModuleForm(forms.ModelForm):
    """
    Form for creating and updating Module objects.
    """
    class Meta:
        model = Module
        fields = ['title', 'description', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('title', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('description', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('order', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Save Module', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )

class LessonForm(forms.ModelForm):
    """
    Form for creating and updating Lesson objects.
    """
    class Meta:
        model = Lesson
        fields = ['title', 'description', 'order']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('title', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('description', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('order', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Save Lesson', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )

class ContentForm(forms.ModelForm):
    """
    Form for creating and updating Content objects.
    Handles conditional display of fields based on content_type.
    """
    class Meta:
        model = Content
        fields = ['title', 'content_type', 'file', 'text_content', 'video_url', 'duration', 'order']
        widgets = {
            'text_content': forms.Textarea(attrs={'rows': 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('title', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('content_type', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            # These fields will be conditionally shown/hidden via JavaScript in the template
            Field('file', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('text_content', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('video_url', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('duration', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('order', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Save Content', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )
   

class QuizDetailsForm(forms.ModelForm):
    allow_multiple_correct = forms.BooleanField(
        label="Allow multiple correct answers per question?",
        required=False,
        widget=forms.CheckboxInput(
            attrs={'class': 'form-checkbox h-5 w-5 text-indigo-600'}
        )
    )
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'pass_percentage', 'max_attempts', 'allow_multiple_correct']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

# Form for a single Option
class OptionForm(forms.ModelForm):
    """
    Form for individual answer options within a question.
    """
    class Meta:
        model = Option
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-checkbox h-4 w-4 text-green-600 border-gray-300 rounded focus:ring-green-500'}),
        }

# Custom BaseInlineFormSet for Options to enforce exactly one correct answer
class BaseOptionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        correct_options_count = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                if form.cleaned_data.get('is_correct'):
                    correct_options_count += 1
        
        if correct_options_count < 1:
            raise forms.ValidationError("Each question must have at least one correct option.")


# Inline formset for Options (exactly 4 options per question, one correct)
OptionFormSet = inlineformset_factory(
    Question,
    Option,
    form=OptionForm,
    formset=BaseOptionFormSet,
    extra=4,
    min_num=4,
    max_num=4,
    validate_min=True,
    can_delete=False,
    labels={
        'text': 'Option Text',
        'is_correct': 'Is Correct?'
    }
)

# Form for a single Question
class QuestionForm(forms.ModelForm):
    """
    Form for individual quiz questions.
    """
    class Meta:
        model = Question
        fields = ['text', 'order']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-textarea mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}),
        }

# Inline formset for Questions within a Quiz
QuestionFormSet = inlineformset_factory(
    Quiz,
    Question,
    form=QuestionForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
    labels={
        'text': 'Question Text',
        'order': 'Order'
    }
)

# Form for assigning a Quiz to a Course
class QuizAssignmentForm(forms.Form):
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(), # Queryset will be set dynamically in the view
        empty_label="Select a course",
        label="Assign to Course",
        help_text="Select a course to assign this quiz as its main assessment. Only courses without an existing quiz are shown."
    )

    def __init__(self, *args, **kwargs):
        instructor_user = kwargs.pop('instructor_user', None) # Expecting the request.user here
        super().__init__(*args, **kwargs)
        if instructor_user:
            # Filter courses taught by this instructor that do not already have a quiz linked
            self.fields['course'].queryset = Course.objects.filter(
                instructor=instructor_user
            ).exclude(quiz__isnull=False).order_by('title')

class AssignCourseForm(forms.ModelForm):
    """
    A form for instructors to assign a course to a student.
    """
    class Meta:
        model = Enrollment
        fields = ['student', 'course']

    # Customize the queryset to filter for non-staff users (students)
    student = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=False, is_instructor=False).order_by('first_name', 'last_name'),
        label="Select Student",
        widget=forms.Select(attrs={'class': 'form-select block w-full mt-1 rounded-md'})
    )
    
    # We override this method to display the student's full name
    # It will use the full name if available, otherwise it falls back to the username.
    def label_from_instance(self, obj):
        full_name = obj.get_full_name()
        if full_name:
            return f"{full_name} ({obj.username})"
        return obj.username

    course = forms.ModelChoiceField(
        queryset=Course.objects.all().order_by('title'),
        label="Select Course",
        widget=forms.Select(attrs={'class': 'form-select block w-full mt-1 rounded-md'})
    )


# Form for CSV Upload
class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload Questions CSV",
        help_text="Upload a CSV file with questions and options. See sample template for format."
    )

# Student-facing Quiz Taking Form
class TakeQuizForm(forms.Form):
    """
    A dynamic form for taking a quiz.
    It generates fields based on the questions associated with a given Quiz instance.
    """
    def __init__(self, *args, **kwargs):
        self.quiz = kwargs.pop('quiz', None)
        super().__init__(*args, **kwargs)

        if not self.quiz:
            raise ValueError("Quiz instance must be provided to TakeQuizForm.")

        for question in self.quiz.questions.all().order_by('order'):
            choices = [(option.id, option.text) for option in question.options.all()]
            
            if self.quiz.allow_multiple_correct or question.options.filter(is_correct=True).count() > 1:
                # Multiple correct answers → checkboxes
                self.fields[f'question_{question.id}'] = forms.MultipleChoiceField(
                    label=f"{question.order}. {question.text}",
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox h-4 w-4 text-indigo-600'}),
                    required=True,
                )
            else:
                # Single correct answer → radio buttons
                self.fields[f'question_{question.id}'] = forms.ChoiceField(
                    label=f"{question.order}. {question.text}",
                    choices=choices,
                    widget=forms.RadioSelect(attrs={'class': 'form-radio h-4 w-4 text-indigo-600'}),
                    required=True,
                )
                self.fields[f'question_{question.id}'].widget.attrs['data-question-id'] = question.id

class SingleQuestionForm(forms.Form):
    """
    A form for displaying and handling a single question.
    This is the ideal form to use for a paginated quiz.
    """
    def __init__(self, question, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get all options for the current question
        options = question.options.all()

        # Create a list of tuples for the choices, using only the option text as the label
        choices = [(option.id, option.text) for option in options]

        if question.options.filter(is_correct=True).count() > 1 or question.quiz.allow_multiple_correct:
            field_class = forms.MultipleChoiceField
            widget_class = forms.CheckboxSelectMultiple(attrs={'class': 'form-checkbox h-4 w-4 text-indigo-600'})
        else:
            field_class = forms.ChoiceField
            widget_class = forms.RadioSelect(attrs={'class': 'form-radio h-4 w-4 text-indigo-600'})

        self.fields[f'question_{question.id}'] = field_class(
            choices=choices,
            widget=widget_class,
            label=question.text,
            required=True
        )


class RatingForm(forms.ModelForm):
    """
    A form for students to submit a course rating and review.
    """
    rating = forms.IntegerField(
        widget=forms.HiddenInput(),
        required=True,
        min_value=1,
        max_value=5
    )
    review = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Write your review here (optional)...',
            'rows': 4,
            'class': 'w-full px-3 py-2 text-gray-700 border rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600 transition-shadow'
        }),
        required=False
    )

    class Meta:
        model = Rating
        fields = ['rating', 'review']


class SupportTicketForm(forms.ModelForm):
    """
    Form for students to create a new support ticket.
    """
    class Meta:
        model = SupportTicket
        fields = ['subject', 'description']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter a brief subject'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'rows': 5,
                'placeholder': 'Describe your issue in detail'
            }),
        }
        
class GroupPermissionForm(forms.ModelForm):
    """
    A custom ModelForm for managing Group permissions and members,
    with a FormHelper for styling via crispy_forms.
    This version excludes certain permissions related to internal models.
    """
    
    # Field to select permissions. We'll filter this to show only relevant permissions.
    permissions = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissions"
    )

    # Field to select users to add to or remove from the group.
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by('username'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Users in this Group"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions', 'users']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # ====================================================================
        # EXCLUDING PERMISSIONS FROM CERTAIN MODELS
        # We will build a list of models for which we DO want to manage
        # permissions. Models like StudentContentProgress, StudentQuizAttempt,
        # and Certificate are typically managed by application logic, so
        # we'll exclude them from the permissions list.
        # ====================================================================

        # Models to include permissions for
        lms_models_to_include = [
            Course, Module, Lesson, Certificate, Content, Enrollment, 
            Quiz, Question, Option, User # Including User for user management permissions
        ]
        
        # Get the content types for the included models
        lms_content_types = [ContentType.objects.get_for_model(model) for model in lms_models_to_include]
        
        # Filter the permissions queryset to only include permissions for the specified models
        self.fields['permissions'].queryset = Permission.objects.filter(
            content_type__in=lms_content_types
        ).order_by('content_type__app_label', 'content_type__model', 'codename')

        # If a group instance is provided, pre-populate the form fields
        if self.instance.pk:
            self.fields['permissions'].initial = self.instance.permissions.all()
            self.fields['users'].initial = self.instance.user_set.all()

        # Set up the FormHelper for crispy_forms layout
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('name', css_class='form-control'),
            Row(
                Column(
                    HTML('<h3 class="text-xl font-semibold text-gray-800 mb-4 border-b pb-2">Assign Permissions</h3>'),
                    Field('permissions', css_class='form-check-input', css_id='id_permissions'),
                    css_class='md:col-span-1'
                ),
                Column(
                    HTML('<h3 class="text-xl font-semibold text-gray-800 mb-4 border-b pb-2">Add Users to Group</h3>'),
                    Field('users', css_class='form-check-input', css_id='id_users'),
                    css_class='md:col-span-1'
                ),
                css_class='grid md:grid-cols-2 gap-8'
            ),
            Submit('submit', 'Save Group', css_class='mt-6 px-6 py-3 bg-indigo-600 text-white font-bold rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 transition duration-150 ease-in-out shadow-md float-right')
        )
        self.fields['name'].widget.attrs.update({'class': 'w-full px-3 py-2 border rounded-lg text-gray-700 focus:outline-none focus:border-indigo-500'})

    def save(self, commit=True):
        """
        Custom save method to handle updating both group permissions and users.
        """
        group = super().save(commit=False)
        if commit:
            group.save()
            # Update the group's permissions
            group_permissions = self.cleaned_data.get('permissions')
            group.permissions.set(group_permissions)

            # Update the users in the group
            group_users = self.cleaned_data.get('users')
            group.user_set.set(group_users)
        
        return group