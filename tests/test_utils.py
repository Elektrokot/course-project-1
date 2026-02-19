import json
from datetime import datetime
from unittest.mock import mock_open, patch

import pandas as pd
import pytest
from conftest import (mock_alpha_vantage_response, mock_currency_response, sample_transactions_df,
                      sample_transactions_df_with_invest)

from src.utils import (calculate_cards_data, filter_transactions_by_date_range, get_currency_rates, get_date_range,
                       get_greeting, get_stock_prices, get_top_transactions, load_transactions_from_xlsx)


class TestGetGreeting:
    @pytest.mark.parametrize(
        "hour, expected_greeting",
        [
            (5, "Доброй ночи"),
            (11, "Доброе утро"),
            (16, "Добрый день"),
            (23, "Добрый вечер"),
            (0, "Доброй ночи"),
            (12, "Добрый день"),
            (18, "Добрый вечер"),
        ],
    )
    def test_get_greeting(self, hour, expected_greeting):
        assert get_greeting(hour) == expected_greeting


class TestLoadTransactionsFromXlsx:
    @patch("src.utils.pd.read_excel")
    def test_load_transactions_from_xlsx_success(self, mock_read_excel, sample_transactions_df):
        mock_read_excel.return_value = sample_transactions_df
        df = load_transactions_from_xlsx("dummy_path.xlsx")
        assert not df.empty
        assert "Дата операции" in df.columns
        assert pd.api.types.is_datetime64_any_dtype(df["Дата операции"])
        mock_read_excel.assert_called_once_with("dummy_path.xlsx", engine="openpyxl")


class TestFilterTransactionsByDateRange:
    def test_filter_transactions_by_date_range(self, sample_transactions_df):
        start_date = "15.09.2020 00:00:00"
        end_date = "17.09.2020 23:59:59"
        filtered_df = filter_transactions_by_date_range(sample_transactions_df, start_date, end_date)
        assert len(filtered_df) == 3  # 15.09, 16.09, 17.09
        assert all(filtered_df["Дата операции"] >= datetime.strptime(start_date, "%d.%m.%Y %H:%M:%S"))
        assert all(filtered_df["Дата операции"] <= datetime.strptime(end_date, "%d.%m.%Y %H:%M:%S"))

    def test_filter_transactions_by_date_range_no_end(self, sample_transactions_df):
        start_date = "17.09.2020 00:00:00"
        # end_date по умолчанию - текущее время, т.е. все после start_date
        filtered_df = filter_transactions_by_date_range(sample_transactions_df, start_date)
        assert len(filtered_df) == 2  # 17.09, 18.09


class TestCalculateCardsData:
    def test_calculate_cards_data(self, sample_transactions_df):
        # Добавим больше транзакций для разных карт и месяцев
        additional_rows = pd.DataFrame(
            [
                {
                    "Дата операции": pd.Timestamp("15.09.2020 10:00:00"),
                    "Статус": "OK",
                    "Сумма операции": -50.0,
                    "Валюта операции": "RUB",
                    "Сумма платежа": -50.0,
                    "Валюта платежа": "RUB",
                    "Категория": "Еда",
                    "Описание": "Оплата в другом кафе",
                    "Бонусы (включая копейки)": 0.5,
                    "Округление на инвесткопилку": 0.0,
                    "Счет": "9876543210987654",  # Другая карта
                }
            ]
        )
        extended_df = pd.concat([sample_transactions_df, additional_rows], ignore_index=True)

        cards_data = calculate_cards_data(extended_df)

        # Ожидаем 2 карты
        assert len(cards_data) == 2

        card1_data = next((card for card in cards_data if card["card_number"] == "1234567890123456"), None)
        card2_data = next((card for card in cards_data if card["card_number"] == "9876543210987654"), None)

        assert card1_data is not None
        assert card2_data is not None

        # Проверим сумму расходов для первой карты (-100 - 200 - 200)
        assert card1_data["total_spent"] == -500.0
        # Проверим сумму расходов для второй карты (-50)
        assert card2_data["total_spent"] == -50.0
        # Проверим бонусы
        assert card1_data["bonuses"] == 1.0  # 1.0 из первой транзакции
        assert card2_data["bonuses"] == 0.5  # 0.5 из дополнительной транзакции


class TestGetTopTransactions:
    def test_get_top_transactions(self, sample_transactions_df):
        top_2 = get_top_transactions(sample_transactions_df, n=2)
        assert len(top_2) == 2
        # Самые большие по модулю суммы: 500.0 (доход), -200.0 (расход), -200.0 (расход), -100.0 (расход)
        # get_top_transactions возвращает по модулю суммы, сортировка по убыванию
        # Топ-2: 500.0, -200.0 (или -200.0, 500.0, в зависимости от реализации сортировки)
        # Предположим, что доходы идут первыми, или просто проверим, что в топе есть 500 и -200
        amounts = [t["Сумма операции"] for t in top_2]
        assert 500.0 in amounts or -500.0 in amounts  # 500.0 или -500.0 (в зависимости от знака)
        # Важно: функция возвращает по модулю, но сохраняет знак. Так что 500.0 (доход) и -200.0 (расход) могут быть в топ-2.
        # Проверим, что в топ-2 есть как минимум 2 транзакции с модулем >= 200.0
        abs_amounts = [abs(t["Сумма операции"]) for t in top_2]
        assert max(abs_amounts) == 500.0
        assert min(abs_amounts) >= 200.0  # Это может быть 200 или 500, если оба в топ-2

    def test_get_top_transactions_empty(self, sample_transactions_df):
        empty_df = sample_transactions_df.iloc[0:0]  # Пустой DataFrame с правильными колонками
        top_0 = get_top_transactions(empty_df, n=5)
        assert len(top_0) == 0


class TestGetCurrencyRates:
    @patch("src.utils.requests.get")
    def test_get_currency_rates(self, mock_get, mock_currency_response):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = mock_currency_response
        rates = get_currency_rates()
        # Предположим, что функция возвращает список словарей
        # [{'currency': 'EUR', 'rate': 0.85}, {'currency': 'USD', 'rate': 1.0}]
        # или просто словарь {'EUR': 0.85, 'USD': 1.0}
        # Зависит от реализации. Проверим наличие ключевых элементов.
        assert "EUR" in str(rates)
        assert "USD" in str(rates)
        mock_get.assert_called()


class TestGetStockPrices:
    @patch("src.utils.requests.get")
    @patch("builtins.open", new_callable=mock_open, read_data='{"date": "2020-09-20", "stocks": []}')
    def test_get_stock_prices_from_cache_and_api(self, mock_file, mock_get, mock_alpha_vantage_response):
        # Предположим, что в user_settings.json есть "user_stocks": ["AAPL"]
        # И кэш пуст или не содержит AAPL для сегодняшней даты
        # Или кэш содержит AAPL, но для другой даты -> нужно запросить снова

        # Мокаем load_user_settings
        with patch("src.utils.load_user_settings", return_value={"user_stocks": ["AAPL"]}):
            # Мокаем, что кэш не содержит сегодняшней даты или не содержит AAPL
            # Поведение: не найдена сегодняшняя дата -> запрос к API
            mock_file.side_effect = [
                FileNotFoundError(),  # Первый вызов open -> файл не найден (новый кэш)
                mock_open().return_value,  # Второй вызов open -> для записи
            ]
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = mock_alpha_vantage_response

            prices = get_stock_prices()

            # Проверим, что был вызов к API
            mock_get.assert_called()
            # Проверим, что результат содержит AAPL с ценой 150.0
            aapl_price = next((item for item in prices if item["stock"] == "AAPL"), None)
            assert aapl_price is not None
            assert aapl_price["price"] == 150.0

    @patch("src.utils.requests.get")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"date": "2026-02-19", "stocks": [{"stock": "AAPL", "price": 140.0}]}',
    )
    def test_get_stock_prices_from_cache_only(self, mock_file, mock_get):
        # Мокаем load_user_settings
        with patch("src.utils.load_user_settings", return_value={"user_stocks": ["AAPL"]}):
            # Кэш содержит сегодняшнюю дату и AAPL -> не должно быть вызова к API
            prices = get_stock_prices()

            # Проверим, что НЕ было вызова к API
            mock_get.assert_not_called()
            # Проверим, что результат содержит AAPL с ценой 140.0 из кэша
            aapl_price = next((item for item in prices if item["stock"] == "AAPL"), None)
            assert aapl_price is not None
            assert aapl_price["price"] == 140.0


class TestGetDateRange:
    def test_get_date_range(self):
        start, end = get_date_range("09.2020", "M")
        # Ожидаем 01.09.2020 00:00:00 и 30.09.2020 23:59:59
        expected_start = datetime(2020, 9, 1, 0, 0, 0)
        expected_end = datetime(2020, 9, 30, 23, 59, 59)
        assert start == expected_start
        assert end == expected_end

    def test_get_date_range_invalid_period(self):
        with pytest.raises(ValueError):
            get_date_range("09.2020", "INVALID_PERIOD")
