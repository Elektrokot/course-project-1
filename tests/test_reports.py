import json
from datetime import datetime, timedelta

import pandas as pd
import pytest
from conftest import sample_transactions_df

from src.reports import spending_by_category, spending_by_weekday, spending_by_workday


class TestSpendingByCategory:
    def test_spending_by_category_found(self, sample_transactions_df):
        category = "Еда"
        date = "20.09.2020"  # В этот период есть транзакция по "Еда"
        result_json = spending_by_category(sample_transactions_df, category, date)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Категория"].lower() == category.lower()
        assert result[0]["Сумма операции"] == -100.0

    def test_spending_by_category_not_found(self, sample_transactions_df):
        category = "Авто"
        date = "20.09.2020"
        result_json = spending_by_category(sample_transactions_df, category, date)
        result = json.loads(result_json)
        assert len(result) == 0

    def test_spending_by_category_case_insensitive(self, sample_transactions_df):
        category = "еДа"
        date = "20.09.2020"
        result_json = spending_by_category(sample_transactions_df, category, date)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Категория"] == "Еда"

    def test_spending_by_category_three_months(self, sample_transactions_df):
        # Создадим DataFrame с транзакциями за последние 3 месяца от даты
        # sample_transactions_df содержит даты в сентябре 2020
        # Проверим, что транзакции находятся, когда дата поиска в октябре
        category = "Еда"
        date = "15.10.2020"  # 3 месяца назад от этой даты охватывает сентябрь
        result_json = spending_by_category(sample_transactions_df, category, date)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Категория"].lower() == category.lower()


class TestSpendingByWeekday:
    def test_spending_by_weekday(self, sample_transactions_df):
        # sample_transactions_df содержит транзакции:
        # 15.09.2020 (вт) - Еда -100.0
        # 16.09.2020 (ср) - Зарплата +500.0 (не трата)
        # 17.09.2020 (чт) - Переводы -200.0
        # 18.09.2020 (пт) - Мобильная связь -200.0
        date = "15.10.2020"
        result_json = spending_by_weekday(sample_transactions_df, date)
        result = json.loads(result_json)

        # Ожидаем траты только по дням недели, где были расходы (< 0)
        # Вт (-100), Чт (-200), Пт (-200)
        # Результат - словарь { "ДеньНедели": сумма_трат }
        expected_days = ["Вторник", "Четверг", "Пятница"]
        for day in expected_days:
            assert day in result

        assert result["Вторник"] == 100.0
        assert result["Четверг"] == 200.0
        assert result["Пятница"] == 200.0
        # Остальные дни должны быть 0.0 или отсутствовать, но если есть в результате, то 0.0
        # Проверим, что, например, Понедельник, если есть, равен 0.0
        assert result.get("Понедельник", 0.0) == 0.0


class TestSpendingByWorkday:
    def test_spending_by_workday(self, sample_transactions_df):
        # sample_transactions_df содержит даты: 15.09.2020 (вт), 16.09.2020 (ср), 17.09.2020 (чт), 18.09.2020 (пт)
        # Все они - рабочие дни.
        # Траты: Вт -100, Чт -200, Пт -200
        date = "15.10.2020"
        result_json = spending_by_workday(sample_transactions_df, date)
        result = json.loads(result_json)

        # Ожидаем словарь { "DD.MM.YYYY": сумма_трат } только для рабочих дней с тратами
        # Ключи - это даты в формате DD.MM.YYYY, извлеченные из Timestamp
        # sample_transactions_df['Дата операции'] - Timestamp
        # groupby(dt.date) в функции даст ключи вида datetime.date(D, M, YYYY)
        # .strftime('%d.%m.%Y') превращает их в строку 'DD.MM.YYYY'
        # Ищем траты по рабочим дням (все в сэмпле рабочие) с отрицательной суммой
        expected_dates = ["15.09.2020", "17.09.2020", "18.09.2020"]  # Только дни с тратами
        for date_key in expected_dates:
            assert date_key in result

        assert result["15.09.2020"] == 100.0  # Еда
        assert result["17.09.2020"] == 200.0  # Переводы
        assert result["18.09.2020"] == 200.0  # Мобильная связь

    def test_spending_by_workday_weekend_excluded(self, sample_transactions_df):
        # Добавим транзакцию в выходной день (например, сб 19.09.2020)
        weekend_row = pd.DataFrame(
            [
                {
                    "Дата операции": pd.Timestamp("19.09.2020 10:00:00"),  # Суббота
                    "Статус": "OK",
                    "Сумма операции": -300.0,
                    "Валюта операции": "RUB",
                    "Сумма платежа": -300.0,
                    "Валюта платежа": "RUB",
                    "Категория": "Развлечения",
                    "Описание": "Кино",
                    "Бонусы (включая копейки)": 3.0,
                    "Округление на инвесткопилку": 0.0,
                    "Счет": "1234567890123456",
                }
            ]
        )
        df_with_weekend = pd.concat([sample_transactions_df, weekend_row], ignore_index=True)

        date = "15.10.2020"
        result_json = spending_by_workday(df_with_weekend, date)
        result = json.loads(result_json)

        # Результат НЕ должен содержать трату от 19.09 (суббота)
        assert "19.09.2020" not in result
        # Но должен содержать траты по рабочим дням
        assert "15.09.2020" in result
        assert "17.09.2020" in result
        assert "18.09.2020" in result
