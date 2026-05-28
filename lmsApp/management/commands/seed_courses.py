from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from lmsApp.models import Course, Module, Lesson, Content, Tag

User = get_user_model()

TAGS = [
    "Python", "Data Science", "Machine Learning", "Marketing", "UX/UI",
    "Web Development", "Django", "React", "Cybersecurity", "Cloud", "AWS",
    "Full-Stack", "Design", "Analytics",
]

course_data = [
    {
        "course_title": "Advanced Python for Data Science",
        "course_description": "Master advanced Python libraries like NumPy, Pandas, and Matplotlib for data analysis and visualization.",
        "category": "expert",
        "price": "49.99",
        "is_published": True,
        "default_duration_days": 45,
        "tags": ["Python", "Data Science", "Analytics"],
        "thumbnail": None,
        "instructor": {
            "username": "data_sci_pro",
            "email": "datasci@example.com",
            "first_name": "Diana",
            "last_name": "Osei",
        },
        "modules": [
            {
                "title": "Advanced Data Structures & NumPy",
                "description": "Deep dive into efficient data handling with Python and the fundamentals of NumPy.",
                "lessons": [
                    {
                        "title": "Lambda Functions & List Comprehensions",
                        "description": "Practical applications of advanced Python syntax.",
                        "content": [
                            {
                                "title": "Lambda Functions Explained",
                                "content_type": "text",
                                "text_content": "A detailed explanation of lambda functions and their use cases in modern Python.",
                                "duration": 5,
                                "order": 1,
                            },
                            {
                                "title": "Advanced Python Lambdas PDF",
                                "content_type": "pdf",
                                "file": "lms_content/advanced_python_lambdas.pdf",
                                "duration": 10,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Introduction to NumPy Arrays",
                        "description": "The foundation of numerical computing in Python.",
                        "content": [
                            {
                                "title": "NumPy Arrays Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=GB9J1X_o3E0",
                                "duration": 20,
                                "order": 1,
                            },
                            {
                                "title": "NumPy Intro Slides",
                                "content_type": "slide",
                                "file": "lms_content/numpy_intro_slides.pptx",
                                "duration": 10,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "NumPy for Vectorization",
                        "description": "Performing operations on entire arrays for speed and efficiency.",
                        "content": [
                            {
                                "title": "Vectorization Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=FqG84m12Q0c",
                                "duration": 18,
                                "order": 1,
                            },
                            {
                                "title": "Vectorized Operations Guide",
                                "content_type": "text",
                                "text_content": "A guide to vectorized operations vs. traditional loops.",
                                "duration": 5,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Exercise: NumPy Operations",
                        "description": "A hands-on coding challenge to practice core NumPy functionalities.",
                        "content": [
                            {
                                "title": "NumPy Operations Exercise",
                                "content_type": "text",
                                "text_content": "Write a script that creates a NumPy array and performs various mathematical operations on it.",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Pandas for Data Manipulation",
                "description": "Using Pandas DataFrames to load, clean, and transform real-world datasets.",
                "lessons": [
                    {
                        "title": "Intro to Pandas DataFrames",
                        "description": "Understanding the core data structure of Pandas.",
                        "content": [
                            {
                                "title": "Pandas DataFrames Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=P_J9wK58d68",
                                "duration": 22,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Data Cleaning with Pandas",
                        "description": "Handling missing values and inconsistent data.",
                        "content": [
                            {
                                "title": "Handling Missing Data",
                                "content_type": "text",
                                "text_content": "Techniques for identifying and handling missing data (NaN) in a DataFrame.",
                                "duration": 8,
                                "order": 1,
                            },
                            {
                                "title": "Pandas Cleaning Guide PDF",
                                "content_type": "pdf",
                                "file": "lms_content/pandas_cleaning_guide.pdf",
                                "duration": 12,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Grouping and Aggregating Data",
                        "description": "Using `groupby` and aggregation functions to summarize data.",
                        "content": [
                            {
                                "title": "GroupBy Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=2AFfB2p_hXo",
                                "duration": 25,
                                "order": 1,
                            },
                            {
                                "title": "Pandas GroupBy Slides",
                                "content_type": "slide",
                                "file": "lms_content/pandas_groupby_slides.pptx",
                                "duration": 10,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Analyze a CSV File",
                        "description": "Complete a full data analysis pipeline using a provided dataset.",
                        "content": [
                            {
                                "title": "CSV Analysis Task Instructions",
                                "content_type": "text",
                                "text_content": "Using a provided CSV file, load the data, clean it, and perform a basic statistical analysis.",
                                "duration": 45,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
    {
        "course_title": "Fundamentals of Digital Marketing",
        "course_description": "Explore the core concepts and strategies behind effective digital marketing campaigns.",
        "category": "beginner",
        "price": "29.99",
        "is_published": True,
        "default_duration_days": 30,
        "tags": ["Marketing", "Analytics"],
        "thumbnail": None,
        "instructor": {
            "username": "marketing_expert",
            "email": "marketing@example.com",
            "first_name": "Amara",
            "last_name": "Mensah",
        },
        "modules": [
            {
                "title": "Introduction to Digital Marketing",
                "description": "The landscape of digital marketing and its key components.",
                "lessons": [
                    {
                        "title": "What is Digital Marketing?",
                        "description": "Defining the field and its importance.",
                        "content": [
                            {
                                "title": "Digital Marketing Overview",
                                "content_type": "text",
                                "text_content": "Digital marketing involves all marketing efforts that use an electronic device or the internet.",
                                "duration": 5,
                                "order": 1,
                            },
                            {
                                "title": "Digital Marketing Intro Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=T6-9jA4fLqY",
                                "duration": 15,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Marketing Channels Overview",
                        "description": "A look at SEO, SEM, social media, and email marketing.",
                        "content": [
                            {
                                "title": "Digital Channels PDF",
                                "content_type": "pdf",
                                "file": "lms_content/digital_channels.pdf",
                                "duration": 15,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Creating a Marketing Persona",
                        "description": "Understanding your target audience.",
                        "content": [
                            {
                                "title": "Buyer Persona Template Slides",
                                "content_type": "slide",
                                "file": "lms_content/buyer_persona_template.pptx",
                                "duration": 10,
                                "order": 1,
                            },
                            {
                                "title": "Persona Creation Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=0h6a_c7VjN0",
                                "duration": 12,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Case Study: Successful Campaigns",
                        "description": "Analyzing real-world examples of effective digital campaigns.",
                        "content": [
                            {
                                "title": "Campaign Analysis Task Instructions",
                                "content_type": "text",
                                "text_content": "Analyze a successful marketing campaign and present your findings on what made it effective.",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Content & Social Media Marketing",
                "description": "Strategies for creating engaging content and building a social media presence.",
                "lessons": [
                    {
                        "title": "Content Strategy Basics",
                        "description": "Planning and creating valuable content.",
                        "content": [
                            {
                                "title": "Content Calendar Guide",
                                "content_type": "text",
                                "text_content": "Developing a content calendar and choosing the right formats for your audience.",
                                "duration": 8,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Social Media Platform Guide",
                        "description": "A breakdown of major platforms and their best uses.",
                        "content": [
                            {
                                "title": "Social Media Platforms Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=fXp1N_p87nQ",
                                "duration": 20,
                                "order": 1,
                            },
                            {
                                "title": "Social Media Guide PDF",
                                "content_type": "pdf",
                                "file": "lms_content/social_media_guide.pdf",
                                "duration": 12,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Email Marketing Fundamentals",
                        "description": "Building an email list and crafting effective newsletters.",
                        "content": [
                            {
                                "title": "Email Marketing Slides",
                                "content_type": "slide",
                                "file": "lms_content/email_marketing_slides.pptx",
                                "duration": 10,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Content Plan",
                        "description": "Develop a 3-month content marketing plan for a fictional company.",
                        "content": [
                            {
                                "title": "Content Plan Task Instructions",
                                "content_type": "text",
                                "text_content": "Create a content plan that includes a social media strategy, blog post ideas, and email newsletter content.",
                                "duration": 45,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
    {
        "course_title": "Introduction to UX/UI Design",
        "course_description": "Learn the principles of user experience (UX) and user interface (UI) design to create intuitive and beautiful digital products.",
        "category": "beginner",
        "price": "39.99",
        "is_published": True,
        "default_duration_days": 30,
        "tags": ["UX/UI", "Design"],
        "thumbnail": None,
        "instructor": {
            "username": "design_master",
            "email": "design@example.com",
            "first_name": "Kofi",
            "last_name": "Asante",
        },
        "modules": [
            {
                "title": "UX Design Principles",
                "description": "Understand user-centered design and the core concepts of usability and accessibility.",
                "lessons": [
                    {
                        "title": "What is UX Design?",
                        "description": "Defining the user experience and its role in product development.",
                        "content": [
                            {
                                "title": "UX Design Intro Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=f_nQ_76v0mQ",
                                "duration": 18,
                                "order": 1,
                            },
                            {
                                "title": "UX Design Process Overview",
                                "content_type": "text",
                                "text_content": "An overview of the UX design process, from research to testing.",
                                "duration": 6,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "User Research Techniques",
                        "description": "Methods for understanding user needs and behaviors.",
                        "content": [
                            {
                                "title": "User Research Guide PDF",
                                "content_type": "pdf",
                                "file": "lms_content/user_research_guide.pdf",
                                "duration": 15,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Information Architecture",
                        "description": "Organizing content to create a logical and intuitive user flow.",
                        "content": [
                            {
                                "title": "Info Architecture Slides",
                                "content_type": "slide",
                                "file": "lms_content/info_architecture_slides.pptx",
                                "duration": 12,
                                "order": 1,
                            },
                            {
                                "title": "Sitemaps & User Flows",
                                "content_type": "text",
                                "text_content": "Exploring sitemaps, user flows, and card sorting.",
                                "duration": 8,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: User Persona Creation",
                        "description": "Create a detailed user persona for a mobile application.",
                        "content": [
                            {
                                "title": "User Persona Task Instructions",
                                "content_type": "text",
                                "text_content": "Based on a provided scenario, create a user persona that includes goals, frustrations, and motivations.",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "UI Design & Prototyping",
                "description": "Learn the visual aspects of design and how to create interactive prototypes.",
                "lessons": [
                    {
                        "title": "Visual Design Principles",
                        "description": "Color theory, typography, and layout basics.",
                        "content": [
                            {
                                "title": "Visual Design Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=zR1C2p52L7s",
                                "duration": 20,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Wireframing & Mockups",
                        "description": "Translating ideas into visual designs.",
                        "content": [
                            {
                                "title": "Wireframing Examples Slides",
                                "content_type": "slide",
                                "file": "lms_content/wireframing_examples.pptx",
                                "duration": 10,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Prototyping Tools",
                        "description": "An overview of tools like Figma, Sketch, and Adobe XD.",
                        "content": [
                            {
                                "title": "Prototyping Tools Comparison",
                                "content_type": "text",
                                "text_content": "A comparison of popular prototyping tools and their key features.",
                                "duration": 7,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Low-Fidelity Prototype",
                        "description": "Design a series of wireframes and a clickable prototype for a simple app.",
                        "content": [
                            {
                                "title": "Low-Fidelity Prototype Task Instructions",
                                "content_type": "text",
                                "text_content": "Using a prototyping tool of your choice, create a low-fidelity prototype for a shopping app.",
                                "duration": 40,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
    {
        "course_title": "React & Django Full-Stack Development",
        "course_description": "Build a complete web application using Django for the backend and React for the frontend.",
        "category": "professional",
        "price": "59.99",
        "is_published": True,
        "default_duration_days": 60,
        "tags": ["Web Development", "Django", "React", "Full-Stack", "Python"],
        "thumbnail": None,
        "instructor": {
            "username": "fullstack_dev",
            "email": "fullstack@example.com",
            "first_name": "Emeka",
            "last_name": "Nwosu",
        },
        "modules": [
            {
                "title": "Django REST API",
                "description": "Creating a robust API backend using Django REST Framework.",
                "lessons": [
                    {
                        "title": "Setting up Django REST Framework",
                        "description": "Installing and configuring DRF.",
                        "content": [
                            {
                                "title": "DRF Setup Instructions",
                                "content_type": "text",
                                "text_content": "Step-by-step instructions for a new Django project with DRF.",
                                "duration": 10,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Serializers & Views",
                        "description": "Converting models into JSON and building API endpoints.",
                        "content": [
                            {
                                "title": "Serializers & Views Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=F0S_F1-4-P0",
                                "duration": 25,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Authentication & Permissions",
                        "description": "Securing your API endpoints.",
                        "content": [
                            {
                                "title": "DRF Auth Guide PDF",
                                "content_type": "pdf",
                                "file": "lms_content/drf_auth_guide.pdf",
                                "duration": 15,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Build a Simple API",
                        "description": "Create a REST API for a simple to-do list.",
                        "content": [
                            {
                                "title": "Simple API Task Instructions",
                                "content_type": "text",
                                "text_content": "Build CRUD endpoints for a to-do list model and protect them with token authentication.",
                                "duration": 60,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Connecting React & Django",
                "description": "Building a dynamic frontend that consumes your Django API.",
                "lessons": [
                    {
                        "title": "React Setup & State Management",
                        "description": "Introduction to functional components and hooks.",
                        "content": [
                            {
                                "title": "React Hooks Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=S8L3kK_sDkY",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Fetching Data from the API",
                        "description": "Using `axios` or the Fetch API to get data from your Django backend.",
                        "content": [
                            {
                                "title": "API Fetch Code Examples",
                                "content_type": "text",
                                "text_content": "Code examples for making GET and POST requests.",
                                "duration": 10,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Building Dynamic UI Components",
                        "description": "Creating reusable components that display data from the API.",
                        "content": [
                            {
                                "title": "React Components Slides",
                                "content_type": "slide",
                                "file": "lms_content/react_components_slides.pptx",
                                "duration": 12,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Full-Stack App",
                        "description": "Create a frontend for the to-do list API from the previous module.",
                        "content": [
                            {
                                "title": "Full-Stack App Task Instructions",
                                "content_type": "text",
                                "text_content": "Using React, build an interface that allows users to view, add, edit, and delete to-do items from your Django API.",
                                "duration": 90,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
    {
        "course_title": "Cybersecurity Fundamentals",
        "course_description": "An introductory course on the core principles of cybersecurity, threat landscapes, and defensive strategies.",
        "category": "beginner",
        "price": "34.99",
        "is_published": True,
        "default_duration_days": 30,
        "tags": ["Cybersecurity"],
        "thumbnail": None,
        "instructor": {
            "username": "cyber_guard",
            "email": "cyber@example.com",
            "first_name": "Yemi",
            "last_name": "Adebayo",
        },
        "modules": [
            {
                "title": "Threat Landscape & Security Principles",
                "description": "Explore common cyber threats and the foundational principles of information security.",
                "lessons": [
                    {
                        "title": "Common Cyber Threats",
                        "description": "Phishing, malware, DDoS attacks, and more.",
                        "content": [
                            {
                                "title": "Cyber Threats Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=aG4C4Bv1E_o",
                                "duration": 20,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "CIA Triad",
                        "description": "Confidentiality, Integrity, and Availability.",
                        "content": [
                            {
                                "title": "CIA Triad Slides",
                                "content_type": "slide",
                                "file": "lms_content/cia_triad_slides.pptx",
                                "duration": 10,
                                "order": 1,
                            },
                            {
                                "title": "CIA Triad Breakdown",
                                "content_type": "text",
                                "text_content": "A detailed breakdown of the CIA Triad as the cornerstone of security.",
                                "duration": 5,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Access Control Models",
                        "description": "Role-Based, Discretionary, and Mandatory Access Control.",
                        "content": [
                            {
                                "title": "Access Control Models Explained",
                                "content_type": "text",
                                "text_content": "An explanation of different access control models and their applications.",
                                "duration": 8,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Security Policy",
                        "description": "Draft a basic security policy for a small company.",
                        "content": [
                            {
                                "title": "Security Policy Task Instructions",
                                "content_type": "text",
                                "text_content": "Create a security policy that addresses password requirements, data handling, and acceptable use of company resources.",
                                "duration": 40,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Defensive Strategies",
                "description": "Learn about the tools and practices used to defend against cyber threats.",
                "lessons": [
                    {
                        "title": "Network Security",
                        "description": "Firewalls, intrusion detection systems, and VPNs.",
                        "content": [
                            {
                                "title": "Network Security Guide PDF",
                                "content_type": "pdf",
                                "file": "lms_content/network_security_guide.pdf",
                                "duration": 15,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Cryptography Basics",
                        "description": "Symmetric vs. Asymmetric encryption.",
                        "content": [
                            {
                                "title": "Cryptography Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=ZfO6bV8lT_c",
                                "duration": 22,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Incident Response Plan",
                        "description": "How to respond to a security breach.",
                        "content": [
                            {
                                "title": "Incident Response Plan Slides",
                                "content_type": "slide",
                                "file": "lms_content/incident_response_plan.pptx",
                                "duration": 12,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Phishing Analysis",
                        "description": "Identify and report on a suspicious email.",
                        "content": [
                            {
                                "title": "Phishing Analysis Task Instructions",
                                "content_type": "text",
                                "text_content": "Analyze a provided phishing email and explain the red flags that indicate it's malicious.",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
    {
        "course_title": "AWS Cloud Practitioner",
        "course_description": "Prepare for the AWS Certified Cloud Practitioner exam with a foundational understanding of AWS services.",
        "category": "professional",
        "price": "44.99",
        "is_published": True,
        "default_duration_days": 45,
        "tags": ["Cloud", "AWS"],
        "thumbnail": None,
        "instructor": {
            "username": "aws_guru",
            "email": "aws@example.com",
            "first_name": "Chidi",
            "last_name": "Okeke",
        },
        "modules": [
            {
                "title": "AWS Core Services",
                "description": "A tour of the most common AWS services including compute, storage, and networking.",
                "lessons": [
                    {
                        "title": "Intro to Cloud Computing",
                        "description": "Understanding the benefits and models of cloud computing.",
                        "content": [
                            {
                                "title": "Cloud Computing Overview",
                                "content_type": "text",
                                "text_content": "A high-level introduction to the benefits of cloud computing over traditional on-premise infrastructure.",
                                "duration": 8,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "EC2 and Compute Services",
                        "description": "Working with virtual machines and other compute resources.",
                        "content": [
                            {
                                "title": "EC2 Services Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=kYI_tPzJ-s4",
                                "duration": 28,
                                "order": 1,
                            },
                            {
                                "title": "EC2 Guide PDF",
                                "content_type": "pdf",
                                "file": "lms_content/ec2_guide.pdf",
                                "duration": 15,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "S3 and Storage Services",
                        "description": "Object storage and other data storage options in AWS.",
                        "content": [
                            {
                                "title": "S3 Storage Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=Jm00Gq9f5Wc",
                                "duration": 20,
                                "order": 1,
                            },
                            {
                                "title": "S3 Slides",
                                "content_type": "slide",
                                "file": "lms_content/s3_slides.pptx",
                                "duration": 10,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: AWS Free Tier Setup",
                        "description": "Set up a free tier account and launch your first EC2 instance.",
                        "content": [
                            {
                                "title": "AWS Free Tier Setup Instructions",
                                "content_type": "text",
                                "text_content": "Follow a step-by-step guide to set up an AWS Free Tier account and launch a basic EC2 instance.",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Billing & Security in AWS",
                "description": "Understanding AWS pricing models and security best practices.",
                "lessons": [
                    {
                        "title": "AWS Pricing and Cost Management",
                        "description": "How to manage costs and understand the billing dashboard.",
                        "content": [
                            {
                                "title": "AWS Pricing Models Overview",
                                "content_type": "text",
                                "text_content": "Exploring the different pricing models: on-demand, reserved, and spot instances.",
                                "duration": 10,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "IAM and User Management",
                        "description": "Identity and Access Management for secure access.",
                        "content": [
                            {
                                "title": "IAM Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=eD1xS57nS54",
                                "duration": 22,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Shared Responsibility Model",
                        "description": "Who is responsible for what in the cloud.",
                        "content": [
                            {
                                "title": "Shared Responsibility Model Slides",
                                "content_type": "slide",
                                "file": "lms_content/aws_shared_responsibility.pptx",
                                "duration": 12,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: IAM Policy",
                        "description": "Write an IAM policy to grant limited access to an S3 bucket.",
                        "content": [
                            {
                                "title": "IAM Policy Task Instructions",
                                "content_type": "text",
                                "text_content": "Create a JSON policy document that grants a user read-only access to a specific S3 bucket.",
                                "duration": 30,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
    {
        "course_title": "Introduction to Machine Learning",
        "course_description": "An introduction to the fundamental concepts and algorithms of machine learning, from supervised to unsupervised learning.",
        "category": "expert",
        "price": "54.99",
        "is_published": True,
        "default_duration_days": 45,
        "tags": ["Machine Learning", "Python", "Data Science", "Analytics"],
        "thumbnail": None,
        "instructor": {
            "username": "ml_guru",
            "email": "ml_guru@example.com",
            "first_name": "Ngozi",
            "last_name": "Eze",
        },
        "modules": [
            {
                "title": "Foundational Concepts",
                "description": "Understanding the core ideas behind machine learning and its various types.",
                "lessons": [
                    {
                        "title": "What is Machine Learning?",
                        "description": "Defining the field and its real-world applications.",
                        "content": [
                            {
                                "title": "Machine Learning Overview",
                                "content_type": "text",
                                "text_content": "A high-level overview of machine learning, its history, and its impact on technology.",
                                "duration": 8,
                                "order": 1,
                            },
                            {
                                "title": "Machine Learning Intro Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=GBd_0fH_p30",
                                "duration": 20,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Supervised Learning",
                        "description": "Introduction to classification and regression algorithms.",
                        "content": [
                            {
                                "title": "Supervised Learning Slides",
                                "content_type": "slide",
                                "file": "lms_content/supervised_learning_slides.pptx",
                                "duration": 15,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Unsupervised Learning",
                        "description": "Clustering and dimensionality reduction techniques.",
                        "content": [
                            {
                                "title": "Clustering Algorithms Explained",
                                "content_type": "text",
                                "text_content": "An explanation of clustering algorithms like K-Means and how they find patterns in data.",
                                "duration": 8,
                                "order": 1,
                            },
                            {
                                "title": "Unsupervised Learning PDF",
                                "content_type": "pdf",
                                "file": "lms_content/unsupervised_learning.pdf",
                                "duration": 15,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Simple Linear Regression",
                        "description": "Build a basic linear regression model from scratch.",
                        "content": [
                            {
                                "title": "Linear Regression Task Instructions",
                                "content_type": "text",
                                "text_content": "Using a provided dataset, implement a simple linear regression model to predict a target variable.",
                                "duration": 50,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Model Evaluation",
                "description": "Learning how to evaluate the performance of your machine learning models.",
                "lessons": [
                    {
                        "title": "Bias-Variance Tradeoff",
                        "description": "Understanding the core challenge of model complexity.",
                        "content": [
                            {
                                "title": "Bias-Variance Tradeoff Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=GBI5d2k60k",
                                "duration": 18,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Validation Techniques",
                        "description": "Cross-validation and other methods for robust evaluation.",
                        "content": [
                            {
                                "title": "K-Fold Cross-Validation Guide",
                                "content_type": "text",
                                "text_content": "A guide to different validation strategies like K-fold cross-validation.",
                                "duration": 8,
                                "order": 1,
                            },
                        ],
                    },
                    {
                        "title": "Performance Metrics",
                        "description": "Accuracy, precision, recall, and F1-score.",
                        "content": [
                            {
                                "title": "ML Metrics Slides",
                                "content_type": "slide",
                                "file": "lms_content/ml_metrics_slides.pptx",
                                "duration": 12,
                                "order": 1,
                            },
                            {
                                "title": "Performance Metrics Video",
                                "content_type": "video",
                                "video_url": "https://www.youtube.com/watch?v=J_lE6r2lWc",
                                "duration": 15,
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "title": "Assignment: Model Comparison",
                        "description": "Compare the performance of two different classification models.",
                        "content": [
                            {
                                "title": "Model Comparison Task Instructions",
                                "content_type": "text",
                                "text_content": "Train a Logistic Regression and a Decision Tree classifier on the same dataset and compare their performance using various metrics.",
                                "duration": 60,
                                "order": 1,
                            },
                        ],
                    },
                ],
            },
        ],
    },
]


class Command(BaseCommand):
    help = 'Seeds the database with initial course, tag, and instructor data for the LMS.'

    def handle(self, *args, **options):
        self.stdout.write("Starting to seed LMS data...\n")

        # -------------------------------------------------------------------
        # STEP 1 — Create all Tags up front so courses can reference them
        # -------------------------------------------------------------------
        self.stdout.write("Creating tags...")
        tag_objects = {}
        for tag_name in TAGS:
            tag_obj, created = Tag.objects.get_or_create(name=tag_name)
            tag_objects[tag_name] = tag_obj
            status = "Created" if created else "Exists"
            self.stdout.write(f"  [{status}] Tag: {tag_name}")
        self.stdout.write("")

        # -------------------------------------------------------------------
        # STEP 2 — Create courses
        # -------------------------------------------------------------------
        for course_info in course_data:
            # ---- Instructor ------------------------------------------------
            instr = course_info["instructor"]
            instructor_user, created = User.objects.get_or_create(
                username=instr["username"],
                defaults={
                    "email": instr["email"],
                    "first_name": instr["first_name"],
                    "last_name": instr["last_name"],
                    "is_staff": True,
                    "is_instructor": True,
                    "is_student": False,
                },
            )
            if created:
                instructor_user.set_password("securepass123")
                instructor_user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created instructor: {instructor_user.get_full_name()} ({instructor_user.email})"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Using existing instructor: {instructor_user.get_full_name()} ({instructor_user.email})"
                    )
                )

            # ---- Course ----------------------------------------------------
            course_kwargs = {
                "title": course_info["course_title"],
                "description": course_info["course_description"],
                "instructor": instructor_user,
                "category": course_info.get("category", "beginner"),
                "is_published": course_info.get("is_published", False),
                "default_duration_days": course_info.get("default_duration_days", 30),
            }
            # price is nullable — only set it when provided
            if course_info.get("price") is not None:
                course_kwargs["price"] = course_info["price"]
            # thumbnail is nullable — only set when a path is provided
            if course_info.get("thumbnail"):
                course_kwargs["thumbnail"] = course_info["thumbnail"]

            course = Course.objects.create(**course_kwargs)

            # ---- Tags (M2M — must be set after the course has a PK) --------
            course_tag_names = course_info.get("tags", [])
            if course_tag_names:
                course.tags.set([tag_objects[name] for name in course_tag_names if name in tag_objects])

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created course: '{course.title}' "
                    f"[{course.category}] "
                    f"| Published: {course.is_published} "
                    f"| Tags: {', '.join(course_tag_names) or 'none'}"
                )
            )

            # ---- Modules ---------------------------------------------------
            for module_index, module_info in enumerate(course_info["modules"], 1):
                module = Module.objects.create(
                    course=course,
                    title=module_info["title"],
                    description=module_info["description"],
                    order=module_index,
                )
                self.stdout.write(f"  Module {module_index}: {module.title}")

                # ---- Lessons -----------------------------------------------
                for lesson_index, lesson_info in enumerate(module_info["lessons"], 1):
                    lesson = Lesson.objects.create(
                        module=module,
                        title=lesson_info["title"],
                        description=lesson_info["description"],
                        order=lesson_index,
                    )
                    self.stdout.write(f"    Lesson {lesson_index}: {lesson.title}")

                    # ---- Content -------------------------------------------
                    for content_info in lesson_info["content"]:
                        content_kwargs = {
                            "lesson": lesson,
                            "title": content_info["title"],
                            "content_type": content_info["content_type"],
                            "order": content_info.get("order", 1),
                            "duration": content_info.get("duration", 0),
                        }
                        if "text_content" in content_info:
                            content_kwargs["text_content"] = content_info["text_content"]
                        if "video_url" in content_info:
                            content_kwargs["video_url"] = content_info["video_url"]
                        if "file" in content_info:
                            content_kwargs["file"] = content_info["file"]

                        Content.objects.create(**content_kwargs)
                        self.stdout.write(
                            f"      + [{content_info['content_type'].upper()}] {content_info['title']} "
                            f"({content_info.get('duration', 0)} min)"
                        )

            self.stdout.write("")  # blank line between courses

        self.stdout.write(self.style.SUCCESS("✅ All LMS seed data created successfully!"))