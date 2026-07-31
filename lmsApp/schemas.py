from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
 
 
class OptionSchema(BaseModel):
    text: str = Field(..., min_length=1, max_length=255)
    is_correct: bool = False
 
 
class QuestionSchema(BaseModel):
    text: str = Field(..., min_length=1)
    is_multi_select: bool = False
    options: List[OptionSchema] = Field(..., min_length=2, max_length=6)
 
    @field_validator("options")
    @classmethod
    def at_least_one_correct(cls, options: List[OptionSchema]) -> List[OptionSchema]:
        if not any(o.is_correct for o in options):
            raise ValueError("Question has no correct option marked.")
        return options
 
 
class QuizSchema(BaseModel):
    title: str = "Final Assessment"
    pass_percentage: int = Field(70, ge=1, le=100)
    questions: List[QuestionSchema] = Field(..., min_length=1)
 
 
class ContentSchema(BaseModel):
    title: str = Field(..., min_length=1)
    content_type: str = "text"
    text_content: str = ""
    # Mermaid.js syntax for a conceptual diagram (flowchart, sequence,
    # hierarchy, etc). Empty string if this content item has no diagram.
    diagram_code: str = ""
    order: int = 1
 
    @field_validator("content_type")
    @classmethod
    def valid_content_type(cls, v: str) -> str:
        allowed = {"video", "pdf", "text", "slide", "image", "diagram"}
        if v not in allowed:
            return "text"
        return v
 
 
class LessonSchema(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    order: int = 1
    contents: List[ContentSchema] = Field(..., min_length=1)
 
 
class ModuleSchema(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    order: int = 1
    lessons: List[LessonSchema] = Field(..., min_length=1)
 
 
class CourseOutlineSchema(BaseModel):
    """Stage 1 output: just the skeleton, no lesson content yet."""
    title: str = Field(..., min_length=1)
    description: str = ""
    category: str = "beginner"
    modules: List[ModuleSchema]
 
    @field_validator("category")
    @classmethod
    def valid_category(cls, v: str) -> str:
        allowed = {"beginner", "expert", "professional"}
        return v if v in allowed else "beginner"
 
 
class ModuleGenerationSchema(BaseModel):
    lessons: List[LessonSchema] = Field(..., min_length=1)
    quiz: QuizSchema
 
 
class CourseGenerationResult(BaseModel):
    """Final assembled result after all stages complete."""
    course: CourseOutlineSchema
    quiz: Optional[QuizSchema] = None
    total_questions_generated: int = 0
    pages_processed: int = 0
    images_extracted: int = 0