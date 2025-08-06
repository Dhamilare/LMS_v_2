from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from lmsApp.models import Course, Module, Lesson, Content

User = get_user_model()

# Data for 6 courses with 2 modules and 4 lessons each
course_data = [
    {
        "course_title": "Advanced Python for Data Science",
        "course_description": "Master advanced Python libraries like NumPy, Pandas, and Matplotlib for data analysis and visualization.",
        "instructor_username": "data_sci_pro",
        "instructor_email": "datasci@example.com",
        "modules": [
            {
                "title": "Module 1: Advanced Data Structures & NumPy",
                "description": "Deep dive into efficient data handling with Python and the fundamentals of NumPy.",
                "lessons": [
                    {
                        "title": "Lambda Functions & List Comprehensions",
                        "description": "Practical applications of advanced Python syntax.",
                        "content": [
                            {"content_type": "text", "text_content": "A detailed explanation of lambda functions and their use cases in modern Python.", "order": 1},
                            {"content_type": "pdf", "file": "lms_content/advanced_python_lambdas.pdf", "order": 2}
                        ]
                    },
                    {
                        "title": "Introduction to NumPy Arrays",
                        "description": "The foundation of numerical computing in Python.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=GB9J1X_o3E0", "order": 1},
                            {"content_type": "slide", "file": "lms_content/numpy_intro_slides.pptx", "order": 2}
                        ]
                    },
                    {
                        "title": "NumPy for Vectorization",
                        "description": "Performing operations on entire arrays for speed and efficiency.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=FqG84m12Q0c", "order": 1},
                            {"content_type": "text", "text_content": "A guide to vectorized operations vs. traditional loops.", "order": 2}
                        ]
                    },
                    {
                        "title": "Exercise: NumPy Operations",
                        "description": "A hands-on coding challenge to practice core NumPy functionalities.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Write a script that creates a NumPy array and performs various mathematical operations on it.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: Pandas for Data Manipulation",
                "description": "Using Pandas DataFrames to load, clean, and transform real-world datasets.",
                "lessons": [
                    {
                        "title": "Intro to Pandas DataFrames",
                        "description": "Understanding the core data structure of Pandas.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=P_J9wK58d68", "order": 1}
                        ]
                    },
                    {
                        "title": "Data Cleaning with Pandas",
                        "description": "Handling missing values and inconsistent data.",
                        "content": [
                            {"content_type": "text", "text_content": "Techniques for identifying and handling missing data (NaN) in a DataFrame.", "order": 1},
                            {"content_type": "pdf", "file": "lms_content/pandas_cleaning_guide.pdf", "order": 2}
                        ]
                    },
                    {
                        "title": "Grouping and Aggregating Data",
                        "description": "Using `groupby` and aggregation functions to summarize data.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=2AFfB2p_hXo", "order": 1},
                            {"content_type": "slide", "file": "lms_content/pandas_groupby_slides.pptx", "order": 2}
                        ]
                    },
                    {
                        "title": "Assignment: Analyze a CSV File",
                        "description": "Complete a full data analysis pipeline using a provided dataset.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Using a provided CSV file, load the data, clean it, and perform a basic statistical analysis.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "course_title": "Fundamentals of Digital Marketing",
        "course_description": "Explore the core concepts and strategies behind effective digital marketing campaigns.",
        "instructor_username": "marketing_expert",
        "instructor_email": "marketing@example.com",
        "modules": [
            {
                "title": "Module 1: Introduction to Digital Marketing",
                "description": "The landscape of digital marketing and its key components.",
                "lessons": [
                    {
                        "title": "What is Digital Marketing?",
                        "description": "Defining the field and its importance.",
                        "content": [
                             {"content_type": "text", "text_content": "Digital marketing involves all marketing efforts that use an electronic device or the internet.", "order": 1},
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=T6-9jA4fLqY", "order": 2}
                        ]
                    },
                    {
                        "title": "Marketing Channels Overview",
                        "description": "A look at SEO, SEM, social media, and email marketing.",
                        "content": [
                            {"content_type": "pdf", "file": "lms_content/digital_channels.pdf", "order": 1}
                        ]
                    },
                    {
                        "title": "Creating a Marketing Persona",
                        "description": "Understanding your target audience.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/buyer_persona_template.pptx", "order": 1},
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=0h6a_c7VjN0", "order": 2}
                        ]
                    },
                    {
                        "title": "Case Study: Successful Campaigns",
                        "description": "Analyzing real-world examples of effective digital campaigns.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Analyze a successful marketing campaign and present your findings on what made it effective.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: Content & Social Media Marketing",
                "description": "Strategies for creating engaging content and building a social media presence.",
                "lessons": [
                    {
                        "title": "Content Strategy Basics",
                        "description": "Planning and creating valuable content.",
                        "content": [
                            {"content_type": "text", "text_content": "Developing a content calendar and choosing the right formats for your audience.", "order": 1}
                        ]
                    },
                    {
                        "title": "Social Media Platform Guide",
                        "description": "A breakdown of major platforms and their best uses.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=fXp1N_p87nQ", "order": 1},
                             {"content_type": "pdf", "file": "lms_content/social_media_guide.pdf", "order": 2}
                        ]
                    },
                    {
                        "title": "Email Marketing Fundamentals",
                        "description": "Building an email list and crafting effective newsletters.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/email_marketing_slides.pptx", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: Content Plan",
                        "description": "Develop a 3-month content marketing plan for a fictional company.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Create a content plan that includes a social media strategy, blog post ideas, and email newsletter content.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "course_title": "Introduction to UX/UI Design",
        "course_description": "Learn the principles of user experience (UX) and user interface (UI) design to create intuitive and beautiful digital products.",
        "instructor_username": "design_master",
        "instructor_email": "design@example.com",
        "modules": [
            {
                "title": "Module 1: UX Design Principles",
                "description": "Understand user-centered design and the core concepts of usability and accessibility.",
                "lessons": [
                    {
                        "title": "What is UX Design?",
                        "description": "Defining the user experience and its role in product development.",
                        "content": [
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=f_nQ_76v0mQ", "order": 1},
                             {"content_type": "text", "text_content": "An overview of the UX design process, from research to testing.", "order": 2}
                        ]
                    },
                    {
                        "title": "User Research Techniques",
                        "description": "Methods for understanding user needs and behaviors.",
                        "content": [
                             {"content_type": "pdf", "file": "lms_content/user_research_guide.pdf", "order": 1}
                        ]
                    },
                    {
                        "title": "Information Architecture",
                        "description": "Organizing content to create a logical and intuitive user flow.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/info_architecture_slides.pptx", "order": 1},
                             {"content_type": "text", "text_content": "Exploring sitemaps, user flows, and card sorting.", "order": 2}
                        ]
                    },
                    {
                        "title": "Assignment: User Persona Creation",
                        "description": "Create a detailed user persona for a mobile application.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Based on a provided scenario, create a user persona that includes goals, frustrations, and motivations.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: UI Design & Prototyping",
                "description": "Learn the visual aspects of design and how to create interactive prototypes.",
                "lessons": [
                    {
                        "title": "Visual Design Principles",
                        "description": "Color theory, typography, and layout basics.",
                        "content": [
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=zR1C2p52L7s", "order": 1}
                        ]
                    },
                    {
                        "title": "Wireframing & Mockups",
                        "description": "Translating ideas into visual designs.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/wireframing_examples.pptx", "order": 1}
                        ]
                    },
                    {
                        "title": "Prototyping Tools",
                        "description": "An overview of tools like Figma, Sketch, and Adobe XD.",
                        "content": [
                            {"content_type": "text", "text_content": "A comparison of popular prototyping tools and their key features.", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: Low-Fidelity Prototype",
                        "description": "Design a series of wireframes and a clickable prototype for a simple app.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Using a prototyping tool of your choice, create a low-fidelity prototype for a shopping app.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "course_title": "React & Django Full-Stack Development",
        "course_description": "Build a complete web application using Django for the backend and React for the frontend.",
        "instructor_username": "fullstack_dev",
        "instructor_email": "fullstack@example.com",
        "modules": [
            {
                "title": "Module 1: Django REST API",
                "description": "Creating a robust API backend using Django REST Framework.",
                "lessons": [
                    {
                        "title": "Setting up Django REST Framework",
                        "description": "Installing and configuring DRF.",
                        "content": [
                             {"content_type": "text", "text_content": "Step-by-step instructions for a new Django project with DRF.", "order": 1}
                        ]
                    },
                    {
                        "title": "Serializers & Views",
                        "description": "Converting models into JSON and building API endpoints.",
                        "content": [
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=F0S_F1-4-P0", "order": 1}
                        ]
                    },
                    {
                        "title": "Authentication & Permissions",
                        "description": "Securing your API endpoints.",
                        "content": [
                             {"content_type": "pdf", "file": "lms_content/drf_auth_guide.pdf", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: Build a Simple API",
                        "description": "Create a REST API for a simple to-do list.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Build CRUD endpoints for a to-do list model and protect them with token authentication.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: Connecting React & Django",
                "description": "Building a dynamic frontend that consumes your Django API.",
                "lessons": [
                    {
                        "title": "React Setup & State Management",
                        "description": "Introduction to functional components and hooks.",
                        "content": [
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=S8L3kK_sDkY", "order": 1}
                        ]
                    },
                    {
                        "title": "Fetching Data from the API",
                        "description": "Using `axios` or the Fetch API to get data from your Django backend.",
                        "content": [
                             {"content_type": "text", "text_content": "Code examples for making GET and POST requests.", "order": 1}
                        ]
                    },
                    {
                        "title": "Building Dynamic UI Components",
                        "description": "Creating reusable components that display data from the API.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/react_components_slides.pptx", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: Full-Stack App",
                        "description": "Create a frontend for the to-do list API from the previous module.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Using React, build an interface that allows users to view, add, edit, and delete to-do items from your Django API.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "course_title": "Cybersecurity Fundamentals",
        "course_description": "An introductory course on the core principles of cybersecurity, threat landscapes, and defensive strategies.",
        "instructor_username": "cyber_guard",
        "instructor_email": "cyber@example.com",
        "modules": [
            {
                "title": "Module 1: Threat Landscape & Security Principles",
                "description": "Explore common cyber threats and the foundational principles of information security.",
                "lessons": [
                    {
                        "title": "Common Cyber Threats",
                        "description": "Phishing, malware, DDoS attacks, and more.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=aG4C4Bv1E_o", "order": 1}
                        ]
                    },
                    {
                        "title": "CIA Triad",
                        "description": "Confidentiality, Integrity, and Availability.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/cia_triad_slides.pptx", "order": 1},
                             {"content_type": "text", "text_content": "A detailed breakdown of the CIA Triad as the cornerstone of security.", "order": 2}
                        ]
                    },
                    {
                        "title": "Access Control Models",
                        "description": "Role-Based, Discretionary, and Mandatory Access Control.",
                        "content": [
                             {"content_type": "text", "text_content": "An explanation of different access control models and their applications.", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: Security Policy",
                        "description": "Draft a basic security policy for a small company.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Create a security policy that addresses password requirements, data handling, and acceptable use of company resources.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: Defensive Strategies",
                "description": "Learn about the tools and practices used to defend against cyber threats.",
                "lessons": [
                    {
                        "title": "Network Security",
                        "description": "Firewalls, intrusion detection systems, and VPNs.",
                        "content": [
                            {"content_type": "pdf", "file": "lms_content/network_security_guide.pdf", "order": 1}
                        ]
                    },
                    {
                        "title": "Cryptography Basics",
                        "description": "Symmetric vs. Asymmetric encryption.",
                        "content": [
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=ZfO6bV8lT_c", "order": 1}
                        ]
                    },
                    {
                        "title": "Incident Response Plan",
                        "description": "How to respond to a security breach.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/incident_response_plan.pptx", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: Phishing Analysis",
                        "description": "Identify and report on a suspicious email.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Analyze a provided phishing email and explain the red flags that indicate it's malicious.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "course_title": "AWS Cloud Practitioner",
        "course_description": "Prepare for the AWS Certified Cloud Practitioner exam with a foundational understanding of AWS services.",
        "instructor_username": "aws_guru",
        "instructor_email": "aws@example.com",
        "modules": [
            {
                "title": "Module 1: AWS Core Services",
                "description": "A tour of the most common AWS services including compute, storage, and networking.",
                "lessons": [
                    {
                        "title": "Intro to Cloud Computing",
                        "description": "Understanding the benefits and models of cloud computing.",
                        "content": [
                             {"content_type": "text", "text_content": "A high-level introduction to the benefits of cloud computing over traditional on-premise infrastructure.", "order": 1}
                        ]
                    },
                    {
                        "title": "EC2 and Compute Services",
                        "description": "Working with virtual machines and other compute resources.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=kYI_tPzJ-s4", "order": 1},
                            {"content_type": "pdf", "file": "lms_content/ec2_guide.pdf", "order": 2}
                        ]
                    },
                    {
                        "title": "S3 and Storage Services",
                        "description": "Object storage and other data storage options in AWS.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=Jm00Gq9f5Wc", "order": 1},
                            {"content_type": "slide", "file": "lms_content/s3_slides.pptx", "order": 2}
                        ]
                    },
                    {
                        "title": "Assignment: AWS Free Tier Setup",
                        "description": "Set up a free tier account and launch your first EC2 instance.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Follow a step-by-step guide to set up an AWS Free Tier account and launch a basic EC2 instance.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: Billing & Security in AWS",
                "description": "Understanding AWS pricing models and security best practices.",
                "lessons": [
                    {
                        "title": "AWS Pricing and Cost Management",
                        "description": "How to manage costs and understand the billing dashboard.",
                        "content": [
                             {"content_type": "text", "text_content": "Exploring the different pricing models: on-demand, reserved, and spot instances.", "order": 1}
                        ]
                    },
                    {
                        "title": "IAM and User Management",
                        "description": "Identity and Access Management for secure access.",
                        "content": [
                             {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=eD1xS57nS54", "order": 1}
                        ]
                    },
                    {
                        "title": "Shared Responsibility Model",
                        "description": "Who is responsible for what in the cloud.",
                        "content": [
                             {"content_type": "slide", "file": "lms_content/aws_shared_responsibility.pptx", "order": 1}
                        ]
                    },
                    {
                        "title": "Assignment: IAM Policy",
                        "description": "Write an IAM policy to grant limited access to an S3 bucket.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Create a JSON policy document that grants a user read-only access to a specific S3 bucket.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
    {
        "course_title": "Introduction to Machine Learning",
        "course_description": "An introduction to the fundamental concepts and algorithms of machine learning, from supervised to unsupervised learning.",
        "instructor_username": "ml_guru",
        "instructor_email": "ml_guru@example.com",
        "modules": [
            {
                "title": "Module 1: Foundational Concepts",
                "description": "Understanding the core ideas behind machine learning and its various types.",
                "lessons": [
                    {
                        "title": "What is Machine Learning?",
                        "description": "Defining the field and its real-world applications.",
                        "content": [
                            {"content_type": "text", "text_content": "A high-level overview of machine learning, its history, and its impact on technology.", "order": 1},
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=GBd_0fH_p30", "order": 2}
                        ]
                    },
                    {
                        "title": "Supervised Learning",
                        "description": "Introduction to classification and regression algorithms.",
                        "content": [
                            {"content_type": "slide", "file": "lms_content/supervised_learning_slides.pptx", "order": 1}
                        ]
                    },
                    {
                        "title": "Unsupervised Learning",
                        "description": "Clustering and dimensionality reduction techniques.",
                        "content": [
                            {"content_type": "text", "text_content": "An explanation of clustering algorithms like K-Means and how they find patterns in data.", "order": 1},
                            {"content_type": "pdf", "file": "lms_content/unsupervised_learning.pdf", "order": 2}
                        ]
                    },
                    {
                        "title": "Assignment: Simple Linear Regression",
                        "description": "Build a basic linear regression model from scratch.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Using a provided dataset, implement a simple linear regression model to predict a target variable.", "order": 1}
                        ]
                    }
                ]
            },
            {
                "title": "Module 2: Model Evaluation",
                "description": "Learning how to evaluate the performance of your machine learning models.",
                "lessons": [
                    {
                        "title": "Bias-Variance Tradeoff",
                        "description": "Understanding the core challenge of model complexity.",
                        "content": [
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=GBI5d2k60k", "order": 1}
                        ]
                    },
                    {
                        "title": "Validation Techniques",
                        "description": "Cross-validation and other methods for robust evaluation.",
                        "content": [
                            {"content_type": "text", "text_content": "A guide to different validation strategies like K-fold cross-validation.", "order": 1}
                        ]
                    },
                    {
                        "title": "Performance Metrics",
                        "description": "Accuracy, precision, recall, and F1-score.",
                        "content": [
                            {"content_type": "slide", "file": "lms_content/ml_metrics_slides.pptx", "order": 1},
                            {"content_type": "video", "video_url": "https://www.youtube.com/watch?v=J_lE6r2lWc", "order": 2}
                        ]
                    },
                    {
                        "title": "Assignment: Model Comparison",
                        "description": "Compare the performance of two different classification models.",
                        "content": [
                             {"content_type": "assignment", "text_content": "Train a Logistic Regression and a Decision Tree classifier on the same dataset and compare their performance using various metrics.", "order": 1}
                        ]
                    }
                ]
            }
        ]
    },
]


class Command(BaseCommand):
    help = 'Seeds the database with initial course data for the LMS.'

    def handle(self, *args, **options):
        self.stdout.write("Starting to seed LMS data...")

        for course_info in course_data:
            # Get or create the instructor user
            instructor_username = course_info["instructor_username"]
            instructor_email = course_info["instructor_email"]
            instructor_user, created = User.objects.get_or_create(
                username=instructor_username,
                defaults={
                    "email": instructor_email,
                    "is_staff": True,
                    "is_instructor": True,
                    "is_student": False,  # Explicitly set to False for instructors
                }
            )

            # Set a password if a new user was created
            if created:
                instructor_user.set_password("securepass123")
                instructor_user.save()
                self.stdout.write(self.style.SUCCESS(f"Created new instructor user: {instructor_user.username}"))
            else:
                self.stdout.write(self.style.WARNING(f"Using existing instructor user: {instructor_user.username}"))

            # Create the Course
            course = Course.objects.create(
                title=course_info["course_title"],
                description=course_info["course_description"],
                instructor=instructor_user
            )
            self.stdout.write(self.style.SUCCESS(f"Created course: {course.title}"))

            # Create Modules
            for module_index, module_info in enumerate(course_info["modules"], 1):
                module = Module.objects.create(
                    course=course,
                    title=module_info["title"],
                    description=module_info["description"],
                    order=module_index
                )
                self.stdout.write(f" - Created module: {module.title}")

                # Create Lessons
                for lesson_index, lesson_info in enumerate(module_info["lessons"], 1):
                    lesson = Lesson.objects.create(
                        module=module,
                        title=lesson_info["title"],
                        description=lesson_info["description"],
                        order=lesson_index
                    )
                    self.stdout.write(f"  - Created lesson: {lesson.title}")

                    # Add Content
                    for content_index, content_info in enumerate(lesson_info["content"], 1):
                        content_data = content_info.copy()
                        content_data.pop('order', None)

                        Content.objects.create(
                            lesson=lesson,
                            order=content_index,
                            **content_data
                        )
                        self.stdout.write(f"    - Added content of type: {content_info['content_type']}")

        self.stdout.write(self.style.SUCCESS("\n✅ All course data seeded successfully!"))

