import pytest

from services.score_calculator import ScoreCalculator


class TestScoreCalculator:
    """ScoreCalculator: ham puan + OBP yerleştirme puanı."""

    def test_zero_nets_say_no_obp_components(self) -> None:
        student_data: dict = {'field_type': 'SAY', 'exam_type': 'TYT+AYT'}
        scores = ScoreCalculator.calculate_all_scores(student_data)
        assert scores['tyt_total_score'] == 100.0
        assert scores['ayt_total_score'] == 100.0
        assert scores['total_score'] == 100.0
        assert scores['obp_score'] == 0.0
        assert scores['rank'] == 0
        assert scores['percentile'] == 0.0

    def test_diploma_full_obp_say(self) -> None:
        student_data: dict = {
            'field_type': 'SAY',
            'exam_type': 'TYT+AYT',
            'diploma_grade': 80.0,
            'student_status': 'student',
        }
        scores = ScoreCalculator.calculate_all_scores(student_data)
        assert scores['obp_score'] == 48.0
        assert scores['tyt_total_score'] == 148.0
        assert scores['ayt_total_score'] == 148.0
        assert scores['total_score'] == 148.0

    def test_placement_broken_halves_obp(self) -> None:
        student_data: dict = {
            'field_type': 'SAY',
            'exam_type': 'TYT+AYT',
            'diploma_grade': 80.0,
            'student_status': 'placement_broken',
        }
        scores = ScoreCalculator.calculate_all_scores(student_data)
        assert scores['obp_score'] == 24.0
        assert scores['total_score'] == 124.0

    def test_no_obp(self) -> None:
        student_data: dict = {
            'field_type': 'SAY',
            'exam_type': 'TYT+AYT',
            'diploma_grade': 80.0,
            'student_status': 'no_obp',
        }
        scores = ScoreCalculator.calculate_all_scores(student_data)
        assert scores['obp_score'] == 0.0
        assert scores['total_score'] == 100.0

    def test_exam_type_tyt_only_uses_tyt_branch(self) -> None:
        student_data: dict = {
            'field_type': 'SAY',
            'exam_type': 'TYT',
            'diploma_grade': 50.0,
            'student_status': 'graduated',
        }
        scores = ScoreCalculator.calculate_all_scores(student_data)
        assert scores['obp_score'] == 30.0
        assert scores['ayt_total_score'] == 0.0
        assert scores['total_score'] == scores['tyt_total_score']
        assert scores['tyt_total_score'] == 130.0

    def test_calculate_all_scores_detailed_tyt_uses_only_tyt_coefficients(self) -> None:
        data: dict = {
            'tyt_turkish_net': 10.0,
            'tyt_math_net': 0.0,
            'tyt_science_net': 0.0,
            'tyt_social_net': 0.0,
        }
        detailed = ScoreCalculator.calculate_all_scores_detailed(
            data,
            diploma_grade=None,
            student_status='no_obp',
        )
        assert detailed['tyt']['raw_score'] == 133.0
