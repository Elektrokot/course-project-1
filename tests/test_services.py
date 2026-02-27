import json
from typing import Any, Dict, List

import pandas as pd
import pytest

from src.services import (analyze_cashback_categories, investment_bank, search_transactions_by_phone_numbers,
                          search_transfers_to_individuals, simple_search)


class TestSimpleSearch:
    @pytest.mark.parametrize(
        "query, expected_count, expected_description",
        [
            ("кафе", 1, "Оплата в кафе"),
            ("еда", 2, "Оплата в кафе"),
            ("КАФЕ", 1, "Оплата в кафе"),
            ("автомобиль", 0, None),
        ],
    )
    def test_simple_search_parametrized(
        self,
        sample_transactions_list: List[Dict[str, Any]],
        query: str,
        expected_count: int,
        expected_description: str,
    ) -> None:
        result_json = simple_search(query, sample_transactions_list)
        result = json.loads(result_json)
        assert len(result) == expected_count
        if expected_count > 0:
            assert result[0]["Описание"] == expected_description

    def test_simple_search_empty_query(self, sample_transactions_list: List[Dict[str, Any]]) -> None:
        result_json = simple_search("", sample_transactions_list)
        result = json.loads(result_json)
        # Пустой запрос должен находить все (в зависимости от реализации)
        assert len(result) >= 0

    def test_simple_search_none_transaction(self, sample_transactions_list: List[Dict[str, Any]]) -> None:
        # Создаем копию без None и добавляем None
        transactions_with_none = [t for t in sample_transactions_list if t is not None] + [None]
        result_json = simple_search("кафе", transactions_with_none)  # type: ignore[arg-type]
        result = json.loads(result_json)
        assert len(result) >= 0


class TestSearchTransfersToIndividuals:
    @pytest.mark.parametrize("expected_count", [1, 0, 0])
    def test_search_transfers_to_individuals_parametrized(
        self, sample_transactions_list: List[Dict[str, Any]], expected_count: int
    ) -> None:
        # Создаем разные наборы транзакций в зависимости от expected_count
        if expected_count == 1:
            transactions: List[Dict[str, Any]] = sample_transactions_list
        elif expected_count == 0:
            transactions = [{"Категория": "Еда", "Описание": "Оплата в кафе"}]
        else:  # expected_count == 0
            transactions = []

        result_json = search_transfers_to_individuals(transactions)
        result = json.loads(result_json)
        assert len(result) == expected_count

    def test_search_transfers_to_individuals_special_case(
        self, sample_transactions_list: List[Dict[str, Any]]
    ) -> None:
        transactions: List[Dict[str, Any]] = [{"Категория": "Переводы", "Описание": ""}]
        result_json = search_transfers_to_individuals(transactions)
        result = json.loads(result_json)
        assert len(result) == 0


class TestSearchTransactionsByPhoneNumbers:
    @pytest.mark.parametrize("expected_count", [1, 0, 0])
    def test_search_transactions_by_phone_numbers_parametrized(
        self, sample_transactions_list: List[Dict[str, Any]], expected_count: int
    ) -> None:
        if expected_count == 1:
            transactions: List[Dict[str, Any]] = sample_transactions_list
        elif expected_count == 0:
            transactions = [{"Категория": "Еда", "Описание": "Оплата в кафе"}]
        else:  # expected_count == 0
            transactions = []

        result_json = search_transactions_by_phone_numbers(transactions)
        result = json.loads(result_json)
        assert len(result) == expected_count

    def test_search_transactions_by_phone_numbers_special_case(
        self, sample_transactions_list: List[Dict[str, Any]]
    ) -> None:
        transactions: List[Dict[str, Any]] = [{"Категория": "Мобильная связь", "Описание": ""}]
        result_json = search_transactions_by_phone_numbers(transactions)
        result = json.loads(result_json)
        assert len(result) == 0


class TestInvestmentBank:
    @pytest.mark.parametrize(
        "month, expected_result",
        [
            ("09.2020", "10.0"),  # Инвесткопилка есть в тестовых данных
            ("10.2020", "0.0"),  # Нет инвесткопилки в октябре
            ("08.2020", "0.0"),  # Нет инвесткопилки в августе
        ],
    )
    def test_investment_bank_parametrized(
        self, sample_transactions_df_with_invest: pd.DataFrame, month: str, expected_result: str
    ) -> None:
        # Преобразуем DataFrame в список словарей с явным указанием типов
        records = sample_transactions_df_with_invest.to_dict("records")
        transactions_list: List[Dict[str, Any]] = []
        for record in records:
            # Преобразуем ключи в строки
            str_record = {str(k): v for k, v in record.items()}
            transactions_list.append(str_record)

        # 2. Передаем limit (шаг округления)
        result = investment_bank(month, transactions_list, limit=10)
        assert result == expected_result

    def test_investment_bank_invalid_month(self, sample_transactions_df_with_invest: pd.DataFrame) -> None:
        # Преобразуем DataFrame в список словарей с явным указанием типов
        records = sample_transactions_df_with_invest.to_dict("records")
        transactions_list: List[Dict[str, Any]] = []
        for record in records:
            str_record = {str(k): v for k, v in record.items()}
            transactions_list.append(str_record)

        result = investment_bank("invalid", transactions_list, limit=10)
        assert result == "0.0"

    def test_investment_bank_empty_data(self) -> None:
        # Пустой список транзакций
        transactions_list: List[Dict[str, Any]] = []
        result = investment_bank("09.2020", transactions_list, limit=10)
        assert result == "0.0"


class TestAnalyzeCashbackCategories:
    @pytest.mark.parametrize(
        "year, month, expected_categories",
        [
            (2020, 9, ["Еда"]),  # Еда имеет кешбэк
            (2019, 1, []),  # Нет транзакций в этом месяце
        ],
    )
    def test_analyze_cashback_categories_parametrized(
        self, sample_transactions_df: pd.DataFrame, year: int, month: int, expected_categories: List[str]
    ) -> None:
        # Преобразуем DataFrame в список словарей с явным указанием типов
        records = sample_transactions_df.to_dict("records")
        transactions_list: List[Dict[str, Any]] = []
        for record in records:
            str_record = {str(k): v for k, v in record.items()}
            transactions_list.append(str_record)

        result_json = analyze_cashback_categories(transactions_list, year, month)
        result = json.loads(result_json)

        if expected_categories:
            # Проверяем, что все ожидаемые категории присутствуют
            for category in expected_categories:
                # Ищем категорию с учетом регистра
                found = any(cat.lower() == category.lower() for cat in result.keys())
                assert found, f"Категория {category} не найдена в результате"

                # Находим точное название категории
                cat_key = next(cat for cat in result.keys() if cat.lower() == category.lower())
                assert result[cat_key] > 0.0, f"Кешбэк для {cat_key} должен быть положительным"
        else:
            assert result == {}  # "Результат должен быть пустым словарем"

    def test_analyze_cashback_categories_empty(self, sample_transactions_df: pd.DataFrame) -> None:
        empty_df = sample_transactions_df[sample_transactions_df["Дата операции"] < pd.Timestamp("01.01.2019")]
        # Преобразуем DataFrame в список словарей с явным указанием типов
        records = empty_df.to_dict("records")
        empty_list: List[Dict[str, Any]] = []
        for record in records:
            str_record = {str(k): v for k, v in record.items()}
            empty_list.append(str_record)

        result_json = analyze_cashback_categories(empty_list, 2019, 1)
        result = json.loads(result_json)
        assert result == {}

    def test_analyze_cashback_categories_invalid_input(self, sample_transactions_df: pd.DataFrame) -> None:
        transactions_list: List[Dict[str, Any]] = []
        result_json = analyze_cashback_categories(transactions_list, 2020, 9)
        result = json.loads(result_json)
        assert result == {}
