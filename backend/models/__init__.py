# Models package - relative import kullanarak circular import'u önle

from .user import User
from .student import Student
from .exam_attempt import ExamAttempt
from .university import University, Department, DepartmentYearlyStats, Recommendation
from .preference import Preference
from .swipe import Swipe
from .forum import ForumPost, ForumComment
from .yok_data import YokUniversity, YokProgram, YokCity, ScoreCalculation
from .agenda import AgendaItem
from .study import StudySession
from .chat import ChatMessage

__all__ = [
    "User",
    "Student",
    "ExamAttempt",
    "University",
    "Department",
    "DepartmentYearlyStats",
    "Recommendation",
    "Preference",
    "Swipe",
    "ForumPost",
    "ForumComment",
    "YokUniversity",
    "YokProgram",
    "YokCity",
    "ScoreCalculation",
    "AgendaItem",
    "StudySession",
    "ChatMessage",
]
