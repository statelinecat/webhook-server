import os
import tkinter as tk
from tkinter import filedialog
from datetime import datetime


def should_include_dir(dir_name):
    """
    Проверяет, нужно ли включать папку в обход
    """
    return not (dir_name.startswith('.') or dir_name.startswith('_'))


def combine_py_files_to_txt():
    # Создаем окно для выбора папки
    root = tk.Tk()
    root.withdraw()  # Скрываем главное окно

    # Выбираем папку
    folder_path = filedialog.askdirectory(title="Выберите папку с .py файлами")

    if not folder_path:
        print("Папка не выбрана. Операция отменена.")
        return

    # Получаем имя папки
    folder_name = os.path.basename(folder_path)

    # Генерируем имя файла с датой и временем
    current_time = datetime.now()
    timestamp = current_time.strftime("%Y%m%d_%H%M%S")
    output_filename = f"{folder_name}_{timestamp}.txt"
    output_filepath = os.path.join(folder_path, output_filename)

    py_files = []

    # Собираем все py файлы
    for root_dir, dirs, files in os.walk(folder_path):
        # Исключаем папки, начинающиеся с точки из дальнейшего обхода
        dirs[:] = [d for d in dirs if should_include_dir(d)]

        for file in files:
            if file.endswith('.py') or file.endswith('.json') or file.endswith('.text'):
                full_path = os.path.join(root_dir, file)
                py_files.append(full_path)

    # Сортируем файлы для упорядоченного объединения
    py_files.sort()

    if not py_files:
        print("Не найдено .py файлов для объединения")
        return

    # Записываем все файлы в один
    with open(output_filepath, 'w', encoding='utf-8') as outfile:
        for py_file in py_files:
            # Записываем путь к файлу с решеткой
            outfile.write(f"# {py_file}\n")

            # Записываем содержимое файла
            try:
                with open(py_file, 'r', encoding='utf-8') as infile:
                    content = infile.read()
                    outfile.write(content)

                # Добавляем пустую строку между файлами для разделения
                outfile.write("\n\n")

            except Exception as e:
                print(f"Ошибка при чтении файла {py_file}: {e}")

    print(f"Операция завершена успешно!")
    print(f"Все .py файлы объединены в: {output_filepath}")
    print(f"Объединено файлов: {len(py_files)}")


if __name__ == "__main__":
    combine_py_files_to_txt()