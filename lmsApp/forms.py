from django import forms
from django.contrib.auth.forms import UserChangeForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field
from .models import *
from django.forms import inlineformset_factory, BaseInlineFormSet, widgets, IntegerField, Textarea
from django_ckeditor_5.widgets import CKEditor5Widget

INTEGER_WIDGET = widgets.NumberInput(attrs={'class': 'w-full p-2 border rounded shadow-sm', 'min': 1, 'max': 365})

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
        fields = ['title', 'description', 'category', 'instructor', 'default_duration_days','price', 'is_published', 'thumbnail', 'tags']
        widgets = {
            'description': CKEditor5Widget(config_name='default', attrs={'data-type': 'ckeditor'}),
            'tags': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }

    default_duration_days = IntegerField(
        label="Default Completion Duration (Days)",
        widget=INTEGER_WIDGET,
        required=False,
        initial=30
    )

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
            'description': CKEditor5Widget(config_name='default', attrs={'data-type': 'ckeditor'}),
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
            'description': CKEditor5Widget(config_name='default', attrs={'data-type': 'ckeditor'}),
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
            'description': CKEditor5Widget(config_name='default', attrs={'data-type': 'ckeditor'}),
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
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'django_ckeditor_5',
            'rows': 5,
            'placeholder': 'Describe your issue in detail',
        }),
        required=False
    )

    class Meta:
        model = SupportTicket
        fields = ['subject', 'description']
        widgets = {
            'subject': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter a brief subject'
            }),
        }

    def clean_description(self):
        description = self.cleaned_data.get('description', '').strip()
        if not description:
            raise forms.ValidationError("Description is required.")
        return description


class PreferenceForm(forms.ModelForm):
    DEPARTMENT_CHOICES = [
        ('IT', 'IT / Software Development'),
        ('Marketing', 'Marketing & Communications'),
        ('Sales', 'Sales & Business Development'),
        ('People Ops', 'People Operations'),
        ('Business Applications', 'Business Applications'),
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


class CourseEvaluationForm(forms.ModelForm):
    # Standard choice list for 1-5 ratings
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    SELECT_WIDGET = widgets.Select(attrs={'class': 'w-full p-2 border rounded shadow-sm'})
    TEXTAREA_WIDGET = Textarea(attrs={'rows': 4, 'class': 'w-full p-2 border rounded shadow-sm'})

    career_relevance_rating = IntegerField(
        label="1. How relevant is this course to your current career path? (1=Low, 5=High)",
        widget=widgets.Select(choices=RATING_CHOICES, attrs={'class': 'w-full p-2 border rounded shadow-sm'})
    )
    course_quality_rating = IntegerField(
        label="2. How would you rate the overall quality of the content? (1=Poor, 5=Excellent)",
        widget=widgets.Select(choices=RATING_CHOICES, attrs={'class': 'w-full p-2 border rounded shadow-sm'})
    )
    instructor_effectiveness_rating = IntegerField(
        label="3. Instructor Effectiveness (1=Poor, 5=Excellent)",
        widget=widgets.Select(choices=RATING_CHOICES, attrs={'class': 'w-full p-2 border rounded shadow-sm'})
    )
    course_structure_rating = IntegerField(
        label="4. Course Structure & Organization (1=Poor, 5=Excellent)",
        widget=widgets.Select(choices=RATING_CHOICES, attrs={'class': 'w-full p-2 border rounded shadow-sm'})
    )
    actionable_feedback = forms.CharField(
        label="5. How do you plan to apply this learning in your daily job responsibilities? (Required for Appraisal)",
        widget=Textarea(attrs={'rows': 4, 'class': 'w-full p-2 border rounded shadow-sm'})
    )
    liked_most = forms.CharField(
        label="6. What specific aspects of the course did you like most?",
        required=False,
        widget=TEXTAREA_WIDGET
    )
    improvement_suggestions = forms.CharField(
        label="7. Suggestions for Improvement (Content, delivery, or structure)",
        required=False,
        widget=TEXTAREA_WIDGET
    )

    class Meta:
        model = CourseEvaluation
        fields = [
            'career_relevance_rating', 
            'course_quality_rating',
            'instructor_effectiveness_rating',
            'course_structure_rating',
            'actionable_feedback',
            'liked_most',
            'improvement_suggestions',
        ]