import json
import secrets
from datetime import datetime
from typing import Optional

from pydantic import EmailStr, field_validator, model_validator
from sqlmodel import Field, SQLModel

COMMON_SUBJECTS = ["English", "Mathematics"]
DEPARTMENT_SUBJECTS = {
    "Science": ["Chemistry", "Physics", "Geography", "Economics"],
    "Art": ["Government", "Literature", "Islamic Religious Studies", "Economics"],
    "Commercial": ["Accounting", "Government", "Geography", "Economics"],
}


class Student(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str = Field(max_length=80)
    middle_name: Optional[str] = Field(default=None, max_length=80)
    last_name: str = Field(max_length=80)
    full_name_key: str = Field(index=True, max_length=240)
    email: str = Field(index=True, max_length=254)
    phone: str = Field(max_length=30)
    student_class: str = Field(max_length=10)
    department: str = Field(max_length=20, index=True)
    subjects_json: str = Field(default="[]")
    exam_number: str = Field(index=True, unique=True, max_length=40)
    download_token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(24),
        index=True,
        unique=True,
        max_length=64,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    @property
    def subjects(self) -> list[str]:
        return json.loads(self.subjects_json)

    def __init__(self, **data):
        subjects = data.pop("subjects", None)
        if subjects is not None:
            data["subjects_json"] = json.dumps(subjects)
        super().__init__(**data)


class StudentCreate(SQLModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    email: EmailStr
    phone: str
    student_class: str
    department: str
    subjects: list[str]

    @field_validator("first_name", "last_name", "middle_name")
    @classmethod
    def validate_name(cls, value):
        if value is not None and (not value.strip() or len(value.strip()) > 80):
            raise ValueError("Please enter a valid name (up to 80 characters).")
        return value.strip() if value else value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value):
        value = value.strip()
        if not 7 <= len(value) <= 30:
            raise ValueError("Please enter a valid phone number.")
        return value

    @model_validator(mode="after")
    def validate_registration(self):
        if self.student_class not in {"SS1", "SS2", "SS3"}:
            raise ValueError("Choose a valid class.")
        if self.department not in DEPARTMENT_SUBJECTS:
            raise ValueError("Choose a valid department.")
        if len(self.subjects) > 6:
            raise ValueError("You can register for no more than 6 subjects.")
        if len(self.subjects) < 2 or not set(COMMON_SUBJECTS).issubset(self.subjects):
            raise ValueError("English and Mathematics are compulsory.")
        if len(set(self.subjects)) != len(self.subjects):
            raise ValueError("Remove duplicate subjects.")
        allowed = set(COMMON_SUBJECTS + DEPARTMENT_SUBJECTS[self.department])
        if not set(self.subjects).issubset(allowed):
            raise ValueError("Choose subjects offered by your selected department.")
        return self
