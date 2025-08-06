# core/forms.py (Instructor is_staff=False Corrected)
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, UserChangeForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, Div, HTML
from .models import *
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.forms import inlineformset_factory, BaseInlineFormSet

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

        # Base Tailwind block style (no shadows)
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
    Custom form for user login with Tailwind block style (no shadow, spacious).
    """

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
        fields = ['title', 'description', 'instructor', 'price', 'is_published', 'thumbnail']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'thumbnail': forms.URLInput(attrs={'placeholder': 'e.g., https://example.com/course_thumb.jpg'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filter the instructor field's queryset to only show users marked as instructors.
        # This will be available for all instructors to choose from.
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
        fields = ['title', 'content_type', 'file', 'text_content', 'video_url', 'order']
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
            Field('order', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Save Content', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )

    def clean(self):
        """
        Custom cleaning to ensure only relevant content fields are populated
        based on the selected content_type.
        """
        cleaned_data = super().clean()
        content_type = cleaned_data.get('content_type')
        file = cleaned_data.get('file')
        text_content = cleaned_data.get('text_content')
        video_url = cleaned_data.get('video_url')

        if content_type == 'video':
            if not video_url and not file:
                raise ValidationError("For video content, either a video URL or a file upload is required.")
            # Clear other fields
            cleaned_data['text_content'] = None
        elif content_type == 'pdf' or content_type == 'slide':
            if not file:
                raise ValidationError(f"For {content_type} content, a file upload is required.")
            # Clear other fields
            cleaned_data['text_content'] = None
            cleaned_data['video_url'] = None
        elif content_type == 'text':
            if not text_content:
                raise ValidationError("For text content, the text field cannot be empty.")
            # Clear other fields
            cleaned_data['file'] = None
            cleaned_data['video_url'] = None
        elif content_type == 'quiz' or content_type == 'assignment':
            cleaned_data['file'] = None
            cleaned_data['text_content'] = None
            cleaned_data['video_url'] = None
        
        return cleaned_data
    

class QuizDetailsForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description', 'pass_percentage', 'max_attempts']
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
        
        if correct_options_count != 1:
            raise forms.ValidationError("Each question must have exactly one correct option.")

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
            
            self.fields[f'question_{question.id}'] = forms.ChoiceField(
                label=f"{question.order}. {question.text}",
                choices=choices,
                widget=forms.RadioSelect(attrs={'class': 'form-radio h-4 w-4 text-indigo-600'}),
                required=True,
            )
            self.fields[f'question_{question.id}'].widget.attrs['data-question-id'] = question.id

