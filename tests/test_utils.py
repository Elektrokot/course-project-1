from datetime import datetime
from typing import Any, Dict
from unittest.mock import mock_open, patch

import pandas as pd
import pytest
import requests

from src.utils import (calculate_cards_data, filter_transactions_by_date_range, get_currency_rates, get_date_range,
                       get_greeting, get_stock_prices, get_top_transactions, load_transactions_from_xlsx)


class TestGetGreeting:
    """Тесты функции приветствия."""

    @pytest.mark.parametrize(
        "hour, expected_greeting",
        [
            (5, "Доброй ночи"),
            (6, "Доброе утро"),
            (11, "Доброе утро"),
            (12, "Добрый день"),
            (17, "Добрый день"),
            (18, "Добрый вечер"),
            (22, "Добрый вечер"),
            (23, "Доброй ночи"),
        ],
    )
    def test_get_greeting_parametrized(self, hour: int, expected_greeting: str) -> None:
        """Тест параметризованных случаев приветствий."""
        assert get_greeting(hour) == expected_greeting

    def test_get_greeting_edge_cases(self) -> None:
        """Проверка граничных значений для функции приветствия."""
        # Проверяем переходы между временами суток
        assert get_greeting(5) == "Доброй ночи"
        assert get_greeting(6) == "Доброе утро"
        assert get_greeting(12) == "Добрый день"
        assert get_greeting(18) == "Добрый вечер"
        assert get_greeting(22) == "Добрый вечер"
        assert get_greeting(23) == "Доброй ночи"


class TestLoadTransactionsFromXlsx:
    """Тесты загрузки транзакций из Excel-файла."""

    @patch("src.utils.pd.read_excel")
    def test_load_transactions_from_xlsx_success(
        self, mock_read_excel: Any, sample_transactions_df: pd.DataFrame
    ) -> None:
        """Успешная загрузка транзакций."""
        mock_read_excel.return_value = sample_transactions_df
        df = load_transactions_from_xlsx("dummy_path.xlsx")

        assert not df.empty
        assert "Дата операции" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["Дата операции"])
        mock_read_excel.assert_called_once_with("dummy_path.xlsx")

    def test_load_transactions_from_xlsx_file_not_found(self) -> None:
        """Тест на обработку ошибки 'файл не найден'."""
        with patch("src.utils.pd.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = FileNotFoundError()
            with pytest.raises(FileNotFoundError):
                load_transactions_from_xlsx("nonexistent.xlsx")

    def test_load_transactions_from_xlsx_invalid_file(self) -> None:
        """Тест на обработку ошибки при чтении некорректного файла."""
        with patch("src.utils.pd.read_excel") as mock_read_excel:
            mock_read_excel.side_effect = Exception("Invalid file")
            with pytest.raises(Exception):
                load_transactions_from_xlsx("invalid.xlsx")

    @patch("src.utils.pd.read_excel")
    def test_load_transactions_from_xlsx_data_types(
        self, mock_read_excel: Any, sample_transactions_df: pd.DataFrame
    ) -> None:
        """Проверка приведения типов данных при загрузке."""
        mock_read_excel.return_value = sample_transactions_df
        df = load_transactions_from_xlsx("dummy_path.xlsx")

        # Проверяем приведение дат
        assert pd.api.types.is_datetime64_any_dtype(df["Дата операции"])
        # Проверяем приведение суммы операции к числу
        assert pd.api.types.is_numeric_dtype(df["Сумма операции"])


class TestFilterTransactionsByDateRange:
    """Тесты фильтрации транзакций по дате."""

    def test_filter_transactions_by_date_range(self, sample_transactions_df: pd.DataFrame) -> None:
        """Фильтрация транзакций с начала месяца по заданную дату."""
        end_date = "17.09.2020 23:59:59"

        # Создаем DataFrame с датами
        test_df = sample_transactions_df.copy()
        filtered_df = filter_transactions_by_date_range(test_df, end_date)

        # Функция фильтрует от начала месяца до target_date
        assert len(filtered_df) == 3  # 15.09, 16.09, 17.09, 20.09 (все в сентябре)

    def test_filter_transactions_by_date_range_no_end(self, sample_transactions_df: pd.DataFrame) -> None:
        """Тест фильтрации по одной дате."""
        target_date_str = "16.09.2020 11:00:00"
        filtered_df = filter_transactions_by_date_range(sample_transactions_df, target_date_str)

        # Должны быть транзакции с 01.09.2020 по 16.09.2020 (включительно)
        assert len(filtered_df) == 2

    def test_filter_transactions_by_date_range_empty(self, sample_transactions_df: pd.DataFrame) -> None:
        """Тест фильтрации с пустым DataFrame."""
        empty_df = pd.DataFrame(columns=sample_transactions_df.columns)
        result = filter_transactions_by_date_range(empty_df, "15.09.2020 00:00:00")
        assert len(result) == 0

    def test_filter_transactions_by_date_range_invalid_dates(self, sample_transactions_df: pd.DataFrame) -> None:
        """Тест с некорректными датами."""
        # Проверяем, что функция выбрасывает ValueError для невалидной даты
        with pytest.raises(ValueError):
            filter_transactions_by_date_range(sample_transactions_df, "invalid_date")

        # Проверяем конкретный случай с некорректной датой
        with pytest.raises(ValueError):
            filter_transactions_by_date_range(sample_transactions_df, "32.13.2020 00:00:00")


class TestCalculateCardsData:
    """Тесты расчета данных по картам."""

    def test_calculate_cards_data(self, sample_transactions_df_with_invest: pd.DataFrame) -> None:
        """Проверка расчета данных по картам с данными о расходах."""
        # Добавим номера карт в DataFrame
        df = sample_transactions_df_with_invest.copy()
        df["Номер карты"] = [
            "1234567890123456",
            "1234567890123456",
            "1234567890123456",
            "9876543210987654",
            "9876543210987654",
        ]

        cards_data = calculate_cards_data(df)

        # Проверяем, что получили данные для 2 карт
        assert len(cards_data) == 2

    def test_calculate_cards_data_empty(self, sample_transactions_df_with_invest: pd.DataFrame) -> None:
        """Тест с пустым DataFrame."""
        df = pd.DataFrame(columns=["Дата операции", "Статус", "Сумма операции", "Номер карты"])
        result = calculate_cards_data(df)
        assert len(result) == 0

    def test_calculate_cards_data_no_expenses(self, sample_transactions_df_with_invest: pd.DataFrame) -> None:
        """Тест, когда нет расходов (только доходы)."""
        df = sample_transactions_df_with_invest.copy()
        # Делаем все суммы положительными (доход)
        df["Сумма операции"] = df["Сумма операции"].abs()
        df["Номер карты"] = ["1234567890123456"] * len(df)

        result = calculate_cards_data(df)

        # При расходах = 0 кэшбэк должен быть 0, но список будет пустым
        assert len(result) == 0


class TestGetTopTransactions:
    """Тесты получения топ-транзакций."""

    def test_get_top_transactions(self, sample_transactions_df_with_invest: pd.DataFrame) -> None:
        """Проверка получения топ-N транзакций."""
        df = sample_transactions_df_with_invest.copy()
        df["Номер карты"] = ["1234567890123456"] * len(df)
        top_3 = get_top_transactions(df, n=3)

        assert len(top_3) == 3
        # Проверяем, что сортировка по убыванию абсолютной величины
        abs_amounts = [abs(t["amount"]) for t in top_3]
        assert abs_amounts == sorted(abs_amounts, reverse=True)

    def test_get_top_transactions_empty(self, sample_transactions_df: pd.DataFrame) -> None:
        """Тест с пустым DataFrame."""
        # Создаем пустой DataFrame с теми же столбцами и типами, что и в реальных данных
        empty_df = pd.DataFrame(columns=sample_transactions_df.columns)

        # Устанавливаем правильные типы данных
        for col in empty_df.columns:
            if col == "Дата операции":
                empty_df[col] = pd.Series(dtype="datetime64[ns]")
            elif col == "Сумма операции":
                empty_df[col] = pd.Series(dtype="float64")
            elif col in ["Описание", "Категория", "Статус", "Номер карты"]:
                empty_df[col] = pd.Series(dtype="string")

        top_0 = get_top_transactions(empty_df, n=5)
        assert len(top_0) == 0

    @pytest.mark.parametrize("n", [0, -1, -5])
    def test_get_top_transactions_invalid_n(self, sample_transactions_df: pd.DataFrame, n: int) -> None:
        """Тест с некорректным значением N."""
        # Убедимся, что DataFrame имеет правильные типы данных
        df = sample_transactions_df.copy()

        result = get_top_transactions(df, n=n)
        assert len(result) == 0


class TestGetCurrencyRates:
    """Тесты получения курсов валют."""

    @patch("src.utils.requests.get")
    def test_get_currency_rates_success(self, mock_get: Any) -> None:
        """Успешное получение курсов валют."""
        # Мокаем ответ от ЦБ РФ
        mock_response = {"Valute": {"USD": {"Value": 75.5}, "EUR": {"Value": 85.2}}}
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_response

        # Мокаем загрузку настроек пользователя
        with patch("src.utils.load_user_settings", return_value={"user_currencies": ["USD", "EUR"]}):
            rates = get_currency_rates()

        assert len(rates) == 2
        assert any(rate["currency"] == "USD" for rate in rates)
        assert any(rate["currency"] == "EUR" for rate in rates)

    @patch("src.utils.requests.get")
    def test_get_currency_rates_api_error(self, mock_get: Any) -> None:
        """Тест обработки ошибки API."""
        mock_get.return_value.status_code = 404

        with patch("src.utils.load_user_settings", return_value={"user_currencies": ["USD"]}):
            rates = get_currency_rates()

        assert rates == []

    @patch("src.utils.requests.get")
    def test_get_currency_rates_network_error(self, mock_get: Any) -> None:
        """Тест обработки сетевой ошибки."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with patch("src.utils.load_user_settings", return_value={"user_currencies": ["USD"]}):
            rates = get_currency_rates()

        assert rates == []


class TestGetStockPrices:
    """Тесты получения цен на акции."""

    @patch("src.utils.requests.get")
    def test_get_stock_prices_success(self, mock_get: Any, mock_alpha_vantage_response: Dict[str, Any]) -> None:
        """Успешное получение цен на акции."""
        # Мокаем ответ от Alpha Vantage
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_alpha_vantage_response

        with patch("src.utils.load_user_settings", return_value={"user_stocks": ["AAPL"]}):
            with patch("builtins.open", mock_open(read_data='{"date": "01.01.2023", "stocks": []}')):
                prices = get_stock_prices()

        assert len(prices) == 1
        assert prices[0]["stock"] == "AAPL"

    @patch("src.utils.requests.get")
    def test_get_stock_prices_cache_hit(self, mock_get: Any) -> None:
        """Тест использования кэша при наличии актуальных данных."""
        mock_get.return_value.status_code = 200

        # Создаем кэш с сегодняшней датой и актуальными данными
        cache_data = {"date": datetime.today().strftime("%d.%m.%Y"), "stocks": [{"stock": "AAPL", "price": 150.0}]}

        with patch("src.utils.load_user_settings", return_value={"user_stocks": ["AAPL"]}):
            with patch("builtins.open", mock_open(read_data=str(cache_data))):
                prices = get_stock_prices()

        assert len(prices) == 1
        assert prices[0]["stock"] == "AAPL"

    @patch("src.utils.requests.get")
    def test_get_stock_prices_empty_user_stocks(self, mock_get: Any) -> None:
        """Тест с пустым списком акций пользователя."""
        with patch("src.utils.load_user_settings", return_value={"user_stocks": []}):
            prices = get_stock_prices()

        assert prices == []


class TestGetDateRange:
    """Тесты функции определения диапазона дат."""

    @pytest.mark.parametrize(
        "period, expected_days_offset",
        [
            ("W", 0),  # Начало недели (понедельник)
            ("M", -14),  # Начало месяца
            ("Y", -268),  # Начало года
            ("ALL", -3652),  # Очень ранняя дата (около 10 лет назад)
        ],
    )
    def test_get_date_range_parametrized(self, period: str, expected_days_offset: int) -> None:
        """Параметризованные тесты для разных периодов."""
        start_date = datetime(2020, 9, 15, 10, 30, 0)

        result_start, result_end = get_date_range(start_date, period)

        assert result_end == start_date

    def test_get_date_range_week(self) -> None:
        """Тест для недельного периода."""
        start_date = datetime(2020, 9, 15, 10, 30, 0)  # вторник
        start_of_week = datetime(2020, 9, 14, 0, 0, 0)  # понедельник

        result_start, result_end = get_date_range(start_date, "W")

        assert result_start == start_of_week
        assert result_end == start_date

    def test_get_date_range_month(self) -> None:
        """Тест для месячного периода."""
        start_date = datetime(2020, 9, 15, 10, 30, 0)
        start_of_month = datetime(2020, 9, 1, 0, 0, 0)

        result_start, result_end = get_date_range(start_date, "M")

        assert result_start == start_of_month
        assert result_end == start_date

    def test_get_date_range_invalid_period(self) -> None:
        """Тест для недопустимого периода."""
        start_date = datetime(2020, 9, 15, 10, 30, 0)

        # Для неизвестного периода возвращается сама дата (день)
        result_start, result_end = get_date_range(start_date, "INVALID")

        assert result_start == start_date
        assert result_end == start_date
