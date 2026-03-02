import json
from unittest.mock import MagicMock, patch

import pandas as pd

from src.views import events_page_data, main

from .conftest import sample_transactions_df


class TestMain:
    @patch("src.views.load_transactions_from_xlsx")
    @patch("src.views.filter_transactions_by_date_range")
    @patch("src.views.calculate_cards_data")
    @patch("src.views.get_top_transactions")
    @patch("src.views.get_currency_rates")
    @patch("src.views.get_stock_prices")
    def test_main_success(
        self,
        mock_get_stock_prices: MagicMock,
        mock_get_currency_rates: MagicMock,
        mock_get_top_transactions: MagicMock,
        mock_calculate_cards_data: MagicMock,
        mock_filter_transactions_by_date_range: MagicMock,
        mock_load_transactions_from_xlsx: MagicMock,
    ) -> None:
        # Подготавливаем моки
        mock_load_transactions_from_xlsx.return_value = sample_transactions_df
        mock_filter_transactions_by_date_range.return_value = sample_transactions_df
        mock_calculate_cards_data.return_value = [{"last_digits": "3456", "total_spent": 100.0, "cashback": 1.0}]
        mock_get_top_transactions.return_value = [
            {"date": "15.09.2020", "amount": -100.0, "category": "Еда", "description": "Оплата в кафе"}
        ]
        mock_get_currency_rates.return_value = [{"currency": "USD", "rate": 1.0}]
        mock_get_stock_prices.return_value = [{"stock": "AAPL", "price": 150.0}]

        result_json = main("15.09.2020 10:00:00")
        result = json.loads(result_json)

        assert "greeting" in result
        assert "cards" in result
        assert "top_transactions" in result
        assert "currency_rates" in result
        assert "stock_prices" in result

        # Проверяем структуру cards
        assert len(result["cards"]) == 1
        assert result["cards"][0]["last_digits"] == "3456"
        assert result["cards"][0]["total_spent"] == 100.0
        assert result["cards"][0]["cashback"] == 1.0

        # Проверяем структуру top_transactions
        assert len(result["top_transactions"]) == 1
        assert result["top_transactions"][0]["date"] == "15.09.2020"
        assert result["top_transactions"][0]["amount"] == -100.0
        assert result["top_transactions"][0]["category"] == "Еда"
        assert result["top_transactions"][0]["description"] == "Оплата в кафе"

        # Проверяем курсы валют
        assert len(result["currency_rates"]) == 1
        assert result["currency_rates"][0]["currency"] == "USD"
        assert result["currency_rates"][0]["rate"] == 1.0

        # Проверяем цены на акции
        assert len(result["stock_prices"]) == 1
        assert result["stock_prices"][0]["stock"] == "AAPL"
        assert result["stock_prices"][0]["price"] == 150.0


class TestEventsPageData:
    def test_events_page_data_success(self, sample_transactions_df: pd.DataFrame) -> None:
        date_str = "15.09.2020 10:00:00"
        period = "M"  # Месяц
        result_json = events_page_data(sample_transactions_df, date_str, period)
        result = json.loads(result_json)

        # Проверяем наличие основных ключей
        assert "expenses" in result
        assert "income" in result
        assert "currency_rates" in result
        assert "stock_prices" in result

        # Проверяем структуру expenses
        assert "total_amount" in result["expenses"]
        assert "main" in result["expenses"]
        assert "transfers_and_cash" in result["expenses"]

        # Проверяем структуру income
        assert "total_amount" in result["income"]
        assert "main" in result["income"]

    def test_events_page_data_no_expenses(self, sample_transactions_df: pd.DataFrame) -> None:
        # Тест с пустым DataFrame для проверки обработки отсутствия транзакций
        empty_df = sample_transactions_df.iloc[0:0]

        date_str = "15.09.2020 10:00:00"
        period = "M"

        result_json = events_page_data(empty_df, date_str, period)
        result = json.loads(result_json)

        assert "expenses" in result
        assert "income" in result

    def test_events_page_data_invalid_date(self, sample_transactions_df: pd.DataFrame) -> None:
        # Проверка обработки неверного формата даты
        date_str = "invalid_date"
        period = "M"

        result_json = events_page_data(sample_transactions_df, date_str, period)
        result = json.loads(result_json)

        # Проверяем наличие основных ключей
        assert "expenses" in result
        assert "income" in result
        assert "currency_rates" in result
        assert "stock_prices" in result

        # Проверяем, что все значения соответствуют ожидаемым типам
        assert isinstance(result["expenses"], dict)
        assert isinstance(result["income"], dict)
        assert isinstance(result["currency_rates"], list)
        assert isinstance(result["stock_prices"], list)

        # Проверяем, что расходы и доходы пустые
        assert result["expenses"]["total_amount"] == 0
        assert len(result["expenses"]["main"]) == 0
        assert len(result["expenses"]["transfers_and_cash"]) == 0
        assert result["income"]["total_amount"] == 0
        assert len(result["income"]["main"]) == 0
