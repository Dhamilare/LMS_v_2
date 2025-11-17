from django import forms
from django.contrib.auth.forms import UserChangeForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field, HTML, Row, Column
from .models import *
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class InstructorCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('email', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('first_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('last_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Create Instructor', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_instructor = True
        user.is_student = False
        user.is_staff = False
        user.set_unusable_password()
        if commit:
            user.save()
        return user


class InstructorUpdateForm(UserChangeForm):
    """
    MODIFIED: Form for Admin to update Instructor accounts.
    - Password field is removed.
    - Email is read-only as it's the primary identifier.
    - 'username' is now just an optional, editable nickname.
    """
    password = None

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('email', 'first_name', 'last_name', 'username')
        help_texts = {f: '' for f in fields}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance.pk:
            self.fields['email'].disabled = True
            
        self.fields['username'].help_text = "Optional nickname. Login is handled by email."

        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('email', css_class='rounded-md shadow-sm border-gray-300 bg-gray-100', readonly=True),
            Field('first_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('last_name', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Field('username', css_class='rounded-md shadow-sm border-gray-300 focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'),
            Submit('submit', 'Update Instructor', css_class='w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 mt-4')
        )


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'description', 'category', 'instructor', 'price', 'is_published', 'thumbnail', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['instructor'].queryset = User.objects.filter(is_instructor=True).order_by('email')

        self.fields['tags'].queryset = Tag.objects.all().order_by('name')

class ModuleForm(forms.ModelForm):
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

class OptionForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}),
            'is_correct': forms.CheckboxInput(attrs={'class': 'form-checkbox h-4 w-4 text-green-600 border-gray-300 rounded focus:ring-green-500'}),
        }

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


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'order']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-textarea mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50', 'rows': 3}),
            'order': forms.NumberInput(attrs={'class': 'form-input mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-300 focus:ring focus:ring-indigo-200 focus:ring-opacity-50'}),
        }


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


class QuizAssignmentForm(forms.Form):
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        empty_label="Select a course",
        label="Assign to Course",
        help_text="Select a course to assign this quiz as its main assessment. Only courses without an existing quiz are shown."
    )

    def __init__(self, *args, **kwargs):
        instructor_user = kwargs.pop('instructor_user', None)
        super().__init__(*args, **kwargs)
        if instructor_user:
            self.fields['course'].queryset = Course.objects.filter(
                instructor=instructor_user
            ).exclude(quiz__isnull=False).order_by('title')


class AssignCourseForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'course']

    student = forms.ModelChoiceField(
        queryset=User.objects.filter(is_staff=False, is_instructor=False).order_by('first_name', 'last_name'),
        label="Select Student",
        widget=forms.Select(attrs={'class': 'form-select block w-full mt-1 rounded-md'})
    )
    
    def label_from_instance(self, obj):
        full_name = obj.get_full_name()
        if full_name:
            return f"{full_name} ({obj.email})"
        return obj.email

    course = forms.ModelChoiceField(
        queryset=Course.objects.all().order_by('title'),
        label="Select Course",
        widget=forms.Select(attrs={'class': 'form-select block w-full mt-1 rounded-md'})
    )


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload Questions CSV",
        help_text="Upload a CSV file with questions and options. See sample template for format."
    )


class TakeQuizForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.quiz = kwargs.pop('quiz', None)
        super().__init__(*args, **kwargs)

        if not self.quiz:
            raise ValueError("Quiz instance must be provided to TakeQuizForm.")

        for question in self.quiz.questions.all().order_by('order'):
            choices = [(option.id, option.text) for option in question.options.all()]
            correct_count = question.options.filter(is_correct=True).count()

            allow_multiple = (
                (self.quiz.allow_multiple_correct and correct_count > 1)
                or correct_count > 1
            )

            field_name = f'question_{question.id}'

            if allow_multiple:
                attrs = {
                    'class': 'form-checkbox h-4 w-4 text-indigo-600',
                    'data-multiple': 'true',
                    'data_multiple': 'true',
                }
                self.fields[field_name] = forms.MultipleChoiceField(
                    label=f"{question.order}. {question.text}",
                    choices=choices,
                    widget=forms.CheckboxSelectMultiple(attrs=attrs),
                    required=True,
                )
            else:
                attrs = {
                    'class': 'form-radio h-4 w-4 text-indigo-600',
                    'data-multiple': 'false',
                    'data_multiple': 'false',
                }
                self.fields[field_name] = forms.ChoiceField(
                    label=f"{question.order}. {question.text}",
                    choices=choices,
                    widget=forms.RadioSelect(attrs=attrs),
                    required=True,
                )

            self.fields[field_name].widget.attrs['data-question-id'] = str(question.id)


class SingleQuestionForm(forms.Form):
    def __init__(self, question, *args, **kwargs):
        super().__init__(*args, **kwargs)

        options = question.options.all()
        choices = [(option.id, option.text) for option in options]
        correct_count = question.options.filter(is_correct=True).count()

        allow_multiple = (
            (question.quiz.allow_multiple_correct and correct_count > 1)
            or correct_count > 1
        )

        field_name = f'question_{question.id}'

        if allow_multiple:
            widget_attrs = {
                'class': 'form-checkbox h-4 w-4 text-indigo-600',
                'data-multiple': 'true',
                'data_multiple': 'true',
            }
            field_class = forms.MultipleChoiceField
            widget = forms.CheckboxSelectMultiple(attrs=widget_attrs)
        else:
            widget_attrs = {
                'class': 'form-radio h-4 w-4 text-indigo-600',
                'data-multiple': 'false',
                'data_multiple': 'false',
            }
            field_class = forms.ChoiceField
            widget = forms.RadioSelect(attrs=widget_attrs)

        self.fields[field_name] = field_class(
            choices=choices,
            widget=widget,
            label=question.text,
            required=True
        )

        self.fields[field_name].widget.attrs['data-question-id'] = str(question.id)


class RatingForm(forms.ModelForm):
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


class PreferenceForm(forms.ModelForm):
    DEPARTMENT_CHOICES = [
        ('IT', 'IT / Software Development'),
        ('Marketing', 'Marketing & Communications'),
        ('Sales', 'Sales & Business Development'),
        ('HR', 'Human Resources'),
        ('Finance', 'Finance & Accounting'),
        ('General', 'General / All Departments'),
    ]

    department = forms.ChoiceField(
        choices=DEPARTMENT_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full p-3 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 shadow-sm'}),
        label="Select Your Department"
    )

    class Meta:
        model = User
        fields = ['department']

class GroupPermissionForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissions"
    )

    # UPDATED: Order users by email, not username
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by('email'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Users in this Group"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions', 'users']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        lms_models_to_include = [
            Course, Module, Lesson, Certificate, Content, Enrollment, 
            Quiz, Question, Option, User
        ]
        
        lms_content_types = [ContentType.objects.get_for_model(model) for model in lms_models_to_include]
        
        self.fields['permissions'].queryset = Permission.objects.filter(
            content_type__in=lms_content_types
        ).order_by('content_type__app_label', 'content_type__model', 'codename')

        if self.instance.pk:
            self.fields['permissions'].initial = self.instance.permissions.all()
            self.fields['users'].initial = self.instance.user_set.all()

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
        group = super().save(commit=False)
        if commit:
            group.save()
            group_permissions = self.cleaned_data.get('permissions')
            group.permissions.set(group_permissions)
            group_users = self.cleaned_data.get('users')
            group.user_set.set(group_users)
        
        return group
    