import json
from unittest.mock import patch

import pandas as pd
import pytest
from conftest import sample_transactions_df

from src.views import events_page_data, main


class TestMainView:
    @patch("src.views.load_transactions_from_xlsx")
    @patch("src.views.get_currency_rates")
    @patch("src.views.get_stock_prices")
    def test_main_view(self, mock_get_stock_prices, mock_get_currency_rates, mock_load_xlsx, sample_transactions_df):
        # Мокаем загрузку транзакций
        mock_load_xlsx.return_value = sample_transactions_df

        # Мокаем вспомогательные функции
        mock_get_currency_rates.return_value = [{"currency": "USD", "rate": 75.0}]
        mock_get_stock_prices.return_value = [{"stock": "AAPL", "price": 150.0}]

        # Вызываем main с датой, например, 17.09.2020 11:30:00 (это среда, день -> Добрый день)
        date_input = "2020-09-17 11:30:00"
        result_json = main(date_input)
        result = json.loads(result_json)

        # Проверяем структуру ответа
        assert "greeting" in result
        assert "cards" in result
        assert "top_transactions" in result
        assert "investment_bank" in result
        assert "cashback_analysis" in result
        assert "currency_rates" in result
        assert "stock_prices" in result

        # Проверяем приветствие (час 11 -> Добрый день)
        assert result["greeting"] == "Добрый день"

        # Проверяем, что вызовы моков произошли
        mock_load_xlsx.assert_called_once_with("data/operations.xlsx")
        mock_get_currency_rates.assert_called()
        mock_get_stock_prices.assert_called()

        # Проверим, что в результатах есть ожидаемые элементы
        # Например, что в top_transactions есть транзакции
        assert isinstance(result["top_transactions"], list)
        # И что в cards есть данные
        assert isinstance(result["cards"], list)


class TestEventsPageData:
    def test_events_page_data_month(self, sample_transactions_df):
        date_input = "2020-09-20 10:00:00"
        period = "M"
        result_json = events_page_data(sample_transactions_df, date_input, period)
        result = json.loads(result_json)

        # Ожидаем, что результат будет списком транзакций за сентябрь 2020
        # sample_transactions_df содержит 4 транзакции в сентябре
        # events_page_data фильтрует по дате и периоду
        # Если фильтр верный, результат должен содержать 4 транзакции
        # Проверим, что результат - это JSON-строка, представляющая список
        assert isinstance(result, list)
        # Уточним: events_page_data возвращает JSON-строку, которую мы parse
        # Предположим, что она возвращает список транзакций
        # В sample_transactions_df все транзакции в сентябре, и date_input в сентябре
        # и period = 'M', значит, должны вернуться все 4 транзакции
        # Однако, если фильтр в events_page_data строго по месяцу (01.09 - 30.09),
        # и date_input указывает на 20.09, то фильтр от 01.09 до 20.09
        # Тогда транзакции до 20.09 (включительно) должны быть: 15.09, 16.09, 17.09, 18.09 -> 4 шт
        assert len(result) == 4

    def test_events_page_data_day(self, sample_transactions_df):
        date_input = "2020-09-17 23:59:59"
        period = "D"
        result_json = events_page_data(sample_transactions_df, date_input, period)
        result = json.loads(result_json)

        # Ожидаем транзакции только за 17.09.2020
        # В sample_transactions_df за 17.09.2020 одна транзакция
        assert len(result) == 1
        assert result[0]["Дата операции"] == "2020-09-17T00:00:00.000"  # или в другом формате, проверим структуру

    def test_events_page_data_all(self, sample_transactions_df):
        date_input = "2020-09-20 10:00:00"
        period = "ALL"
        result_json = events_page_data(sample_transactions_df, date_input, period)
        result = json.loads(result_json)

        # Ожидаем все транзакции до 20.09.2020 (все 4)
        assert len(result) == 4

    def test_events_page_data_invalid_period(self, sample_transactions_df):
        date_input = "2020-09-20 10:00:00"
        period = "INVALID"
        # Предположим, что функция возвращает пустой список или бросает исключение
        # Лучше, чтобы она возвращала пустой список или валидировала период
        # В данном случае, если в коде events_page_data есть проверка, она может вызвать ValueError
        # или просто вернуть пустой список для неверного периода
        # Проверим на пустой список, если логика такова
        result_json = events_page_data(sample_transactions_df, date_input, period)
        result = json.loads(result_json)
        assert len(result) == 0  # или проверить на ValueError, если функция бросает исключение
