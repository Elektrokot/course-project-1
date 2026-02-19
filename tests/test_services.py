import json
from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from conftest import sample_transactions_df, sample_transactions_df_with_invest, sample_transactions_list

from src.services import (analyze_cashback_categories, investment_bank, search_transactions_by_phone_numbers,
                          search_transfers_to_individuals, simple_search)


class TestSimpleSearch:
    def test_simple_search_description(self, sample_transactions_list):
        query = "кафе"
        result_json = simple_search(query, sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Описание"] == "Оплата в кафе"

    def test_simple_search_category(self, sample_transactions_list):
        query = "еда"
        result_json = simple_search(query, sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Категория"] == "Еда"

    def test_simple_search_no_match(self, sample_transactions_list):
        query = "автомобиль"
        result_json = simple_search(query, sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == 0

    def test_simple_search_case_insensitive(self, sample_transactions_list):
        query = "КАФЕ"
        result_json = simple_search(query, sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Описание"] == "Оплата в кафе"


class TestSearchTransfersToIndividuals:
    def test_search_transfers_to_individuals(self, sample_transactions_list):
        result_json = search_transfers_to_individuals(sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Категория"] == "Переводы"
        assert "Иван И." in result[0]["Описание"]

    def test_search_transfers_to_individuals_no_match(self):
        transactions_without_transfer = [
            {"Категория": "Еда", "Описание": "Оплата в кафе"},
            {"Категория": "Зарплата", "Описание": "Перевод от работодателя"},
        ]
        result_json = search_transfers_to_individuals(transactions_without_transfer)
        result = json.loads(result_json)
        assert len(result) == 0


class TestSearchTransactionsByPhoneNumbers:
    def test_search_transactions_by_phone_numbers(self, sample_transactions_list):
        result_json = search_transactions_by_phone_numbers(sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == 1
        assert result[0]["Категория"] == "Мобильная связь"
        assert "+7 995 555-55-55" in result[0]["Описание"]

    def test_search_transactions_by_phone_numbers_no_match(self):
        transactions_without_phones = [
            {"Категория": "Еда", "Описание": "Оплата в кафе"},
            {"Категория": "Зарплата", "Описание": "Перевод от работодателя"},
        ]
        result_json = search_transactions_by_phone_numbers(transactions_without_phones)
        result = json.loads(result_json)
        assert len(result) == 0


class TestInvestmentBank:
    def test_investment_bank(self, sample_transactions_df_with_invest):
        # Транзакция с инвесткопилкой 10.0 RUB на 20.09.2020
        month = "09"
        result_json = investment_bank(month, sample_transactions_df_with_invest)
        result = json.loads(result_json)
        # Ожидаем, что сумма будет 10.0
        assert result["total_investment"] == 10.0

    def test_investment_bank_no_invest(self, sample_transactions_df):
        # sample_transactions_df не содержит инвесткопилки
        month = "09"
        result_json = investment_bank(month, sample_transactions_df)
        result = json.loads(result_json)
        # Ожидаем, что сумма будет 0.0
        assert result["total_investment"] == 0.0

    def test_investment_bank_different_month(self, sample_transactions_df_with_invest):
        # Транзакция с инвесткопилкой в сентябре
        month = "10"  # октябрь
        result_json = investment_bank(month, sample_transactions_df_with_invest)
        result = json.loads(result_json)
        # Ожидаем, что сумма будет 0.0, так как в октябре нет инвесткопилки
        assert result["total_investment"] == 0.0


class TestAnalyzeCashbackCategories:
    def test_analyze_cashback_categories(self, sample_transactions_df):
        # sample_transactions_df содержит:
        # - Еда: -100.0, бонусы 1.0 (1% от 100)
        # - Зарплата: +500.0, бонусы 0.0
        # - Переводы: -200.0, бонусы 0.0
        # - Мобильная связь: -200.0, бонусы 0.0
        year = 2020
        month = 9
        result_json = analyze_cashback_categories(sample_transactions_df, year, month)
        result = json.loads(result_json)
        # Ожидаем, что "Еда" будет иметь наибольший кешбэк (1.0)
        # Результат - список словарей, отсортированный по кешбэку
        assert len(result) > 0
        highest_cb_category = result[0]
        assert highest_cb_category["category"] == "Еда"
        assert highest_cb_category["cashback"] == 1.0

    def test_analyze_cashback_categories_empty(self, sample_transactions_df):
        # Фильтруем DataFrame так, чтобы не было трат за указанный месяц/год
        empty_df = sample_transactions_df[sample_transactions_df["Дата операции"] < pd.Timestamp("01.01.2019")]
        year = 2019
        month = 1
        result_json = analyze_cashback_categories(empty_df, year, month)
        result = json.loads(result_json)
        # Ожидаем пустой список
        assert result == []
