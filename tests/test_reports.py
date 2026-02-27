import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.reports import spending_by_category, spending_by_weekday, spending_by_workday


class TestSpendingByCategory:
    @pytest.mark.parametrize(
        "input_date, expected_count",
        [
            ("15.09.2020", 1),
            ("20.09.2020", 2),
            ("14.06.2020", 0),
        ],
    )
    def test_spending_by_category_with_dates(
        self, sample_transactions_df: pd.DataFrame, input_date: int, expected_count: int
    ) -> None:
        category = "Еда"
        # Патчим декоратор report_to_file, чтобы избежать реальной записи в файл
        with patch("src.reports.report_to_file", lambda x: x):
            result_json = spending_by_category(sample_transactions_df, category, input_date)

        result = json.loads(result_json)
        assert len(result) == expected_count
        if expected_count > 0:
            for transaction in result:
                assert transaction["Категория"].lower() == category.lower()
                assert transaction["Сумма операции"] < 0  # трата

    def test_spending_by_category_case_insensitive(self, sample_transactions_df: pd.DataFrame) -> None:
        category_upper = "ЕДА"
        category_lower = "еда"
        input_date = "20.09.2020"
        with patch("src.reports.report_to_file", lambda x: x):
            result_json_upper = spending_by_category(sample_transactions_df, category_upper, input_date)
            result_json_lower = spending_by_category(sample_transactions_df, category_lower, input_date)

        result_upper = json.loads(result_json_upper)
        result_lower = json.loads(result_json_lower)
        assert result_upper == result_lower

    def test_spending_by_category_no_match(self, sample_transactions_df: pd.DataFrame) -> None:
        category = "Авто"
        input_date = "20.09.2020"
        with patch("src.reports.report_to_file", lambda x: x):
            result_json = spending_by_category(sample_transactions_df, category, input_date)

        result = json.loads(result_json)
        assert result == []


class TestSpendingByWeekday:
    def test_spending_by_weekday_basic(self, sample_transactions_df: pd.DataFrame) -> None:
        input_date = "20.09.2020"
        expected_spending = {
            "Понедельник": 0.0,
            "Вторник": 95.0,  # 15.09
            "Среда": 0.0,  # 16.09 (Зарплата)
            "Четверг": 195.0,  # 17.09
            "Пятница": 200.0,  # 18.09
            "Суббота": 0.0,
            "Воскресенье": 300.0,  # 20.09
        }
        with patch("src.reports.report_to_file", lambda x: x):
            result_json = spending_by_weekday(sample_transactions_df, input_date)

        result = json.loads(result_json)
        assert result == expected_spending

    def test_spending_by_weekday_current_date_fallback(self, sample_transactions_df: pd.DataFrame) -> None:

        expected_spending = {
            "Понедельник": 0.0,
            "Вторник": 95.0,  # 15.09
            "Среда": 0.0,  # 16.09 (Зарплата)
            "Четверг": 195.0,  # 17.09
            "Пятница": 200.0,  # 18.09
            "Суббота": 0.0,
            "Воскресенье": 300.0,  # 20.09
        }
        with patch("src.reports.datetime") as mocked_datetime:
            # Создаем mock-объект для замены класса datetime
            mock_now = MagicMock()
            mock_now.replace.return_value = datetime(2020, 9, 20, 23, 59, 59, 999999)
            mocked_datetime.now.return_value = mock_now
            mocked_datetime.strptime = datetime.strptime  # Сохраняем оригинальный strptime

            with patch("src.reports.report_to_file", lambda x: x):
                result_json = spending_by_weekday(sample_transactions_df, date=None)

        result = json.loads(result_json)
        assert result == expected_spending


class TestSpendingByWorkday:
    def test_spending_by_workday_basic(self, sample_transactions_df: pd.DataFrame) -> None:
        input_date = "25.09.2020"
        expected_result = {"Рабочий день": round(490.0 / 3, 2), "Выходной день": 300.0}
        with patch("src.reports.report_to_file", lambda x: x):
            result_json = spending_by_workday(sample_transactions_df, input_date)

        result = json.loads(result_json)
        assert result == expected_result

    def test_spending_by_workday_no_weekend_spending(self, sample_transactions_df: pd.DataFrame) -> None:

        df_no_weekend = sample_transactions_df[sample_transactions_df["Дата операции"].dt.dayofweek < 5]
        input_date = "25.09.2020"
        expected_result = {"Рабочий день": round(490.0 / 3, 2)}
        with patch("src.reports.report_to_file", lambda x: x):
            result_json = spending_by_workday(df_no_weekend, input_date)

        result = json.loads(result_json)
        assert result == expected_result
        assert "Выходной день" not in result

    def test_spending_by_workday_no_workday_spending(self, sample_transactions_df: pd.DataFrame) -> None:

        df_no_workday = sample_transactions_df[sample_transactions_df["Дата операции"].dt.dayofweek >= 5]
        input_date = "25.09.2020"
        expected_result = {"Выходной день": 300.0}
        with patch("src.reports.report_to_file", lambda x: x):
            result_json = spending_by_workday(df_no_workday, input_date)

        result = json.loads(result_json)
        assert result == expected_result
        assert "Рабочий день" not in result
