import json
import logging
from datetime import datetime

from config import PATH_TO_LOGGER, PATH_TO_OPERATIONS
from src.reports import spending_by_category, spending_by_weekday, spending_by_workday
from src.services import (
    analyze_cashback_categories,
    investment_bank,
    search_transactions_by_phone_numbers,
    search_transfers_to_individuals,
    simple_search,
)
from src.utils import load_transactions_from_xlsx
from src.views import events_page_data
from src.views import main as main_view

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)-8s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(PATH_TO_LOGGER / "app.log", encoding="utf-8"), logging.StreamHandler()],
)


def print_menu() -> None:
    """Печатает меню выбора функции."""
    print("\n--- Меню ---")
    print("1. Главная страница (main)")
    print("2. Страница событий (events_page_data)")
    print("3. Простой поиск (simple_search)")
    print("4. Поиск переводов физ.лицам (search_transfers_to_individuals)")
    print("5. Поиск по телефонным номерам (search_transactions_by_phone_numbers)")
    print("6. Инвесткопилка (investment_bank)")
    print("7. Анализ выгодных категорий кешбэка (analyze_cashback_categories)")
    print("8. Траты по категории (spending_by_category)")
    print("9. Траты по дням недели (spending_by_weekday)")
    print("10. Траты по рабочим дням (spending_by_workday)")
    print("0. Выход")
    print("------------\n")


def save_result_to_file(result_data, function_name):
    """Сохраняет результат в result.json."""
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    output = {"function": function_name, "timestamp": timestamp, "result": result_data}
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\nРезультат сохранен в result.json")


def load_transactions_interactive():
    """Загружает транзакции с возможностью выбора файла."""
    file_path = input("Введите путь к файлу транзакций (по умолчанию 'data/operations.xlsx'): ").strip()
    if not file_path:
        file_path = PATH_TO_OPERATIONS

    try:
        df = load_transactions_from_xlsx(file_path)
        print(f"Файл '{file_path}' успешно загружен. Количество транзакций: {len(df)}")
        return df
    except FileNotFoundError:
        print(f"Ошибка: файл '{file_path}' не найден.")
        return None
    except Exception as e:
        print(f"Ошибка при загрузке файла: {e}")
        return None


def main_loop() -> None:
    """Основной цикл программы."""
    transactions_df = None
    while True:
        print_menu()
        choice = input("Выберите действие (0-10): ").strip()

        if choice == "0":
            print("Выход из программы.")
            break

        # Загружаем транзакции, если они ещё не загружены и функция требует DataFrame
        requires_df = choice in ["2", "8", "9", "10"]
        if requires_df and transactions_df is None:
            transactions_df = load_transactions_interactive()
            if transactions_df is None:
                print("Не удалось загрузить транзакции. Пропуск операции.")
                continue

        # Преобразуем DataFrame в список словарей, если функция принимает список
        transactions_list = transactions_df.to_dict("records") if transactions_df is not None else []

        # --- Выбор функции ---
        try:
            if choice == "1":  # Главная страница
                date_input = input("Введите дату в формате 'DD.MM.YYYY HH:MM:SS' (например, '06.09.2020 09:53:56'): ")
                result = main_view(date_input)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "main")

            elif choice == "2":  # Страница событий
                date_input = input("Введите дату в формате 'DD.MM.YYYY HH:MM:SS' (например, '06.09.2020 09:53:56'): ")
                period_input = input("Введите период ('D', 'W', 'M', 'Y', 'ALL') (по умолчанию 'M'): ").upper().strip()
                if not period_input:
                    period_input = "M"
                result = events_page_data(transactions_df, date_input, period_input)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "events_page_data")

            elif choice == "3":  # Простой поиск
                query_input = input("Введите строку для поиска: ")
                result = simple_search(query_input, transactions_list)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "simple_search")

            elif choice == "4":  # Поиск переводов физ.лицам
                result = search_transfers_to_individuals(transactions_list)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "search_transfers_to_individuals")

            elif choice == "5":  # Поиск по телефонным номерам
                result = search_transactions_by_phone_numbers(transactions_list)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "search_transactions_by_phone_numbers")

            elif choice == "6":  # Инвесткопилка
                month_input = input("Введите месяц в формате 'MM.YYYY' (например, '09.2020'): ")
                result = investment_bank(month_input, transactions_list)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "investment_bank")

            elif choice == "7":  # Анализ выгодных категорий кешбэка
                year_input = int(input("Введите год (например, 2021): "))
                month_input = int(input("Введите месяц (1-12) (например, 12): "))
                result = analyze_cashback_categories(transactions_list, year_input, month_input)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "analyze_cashback_categories")

            elif choice == "8":  # Траты по категории
                category_input = input("Введите категорию (например, 'Супермаркеты'): ")
                date_input = input(
                    "Введите дату в формате 'DD.MM.YYYY' (например, '31.12.2021'), Enter для текущей даты: "
                ).strip()
                if not date_input:
                    date_input = None
                result = spending_by_category(transactions_df, category_input, date_input)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "spending_by_category")

            elif choice == "9":  # Траты по дням недели
                date_input = input(
                    "Введите дату в формате 'DD.MM.YYYY' (например, '31.12.2021'), Enter для текущей даты: "
                ).strip()
                if not date_input:
                    date_input = None
                result = spending_by_weekday(transactions_df, date_input)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "spending_by_weekday")

            elif choice == "10":  # Траты по рабочим дням
                date_input = input(
                    "Введите дату в формате 'DD.MM.YYYY' (например, '31.12.2021'), Enter для текущей даты: "
                ).strip()
                if not date_input:
                    date_input = None
                result = spending_by_workday(transactions_df, date_input)
                print("\n--- Результат: ---")
                print(result)
                save_result_to_file(json.loads(result), "spending_by_workday")

            else:
                print("Неверный выбор. Пожалуйста, введите число от 0 до 10.")

        except KeyboardInterrupt:
            print("\n\nОперация прервана пользователем.")
        except Exception as e:
            print(f"\nПроизошла ошибка при выполнении операции: {e}")


if __name__ == "__main__":
    main_loop()
