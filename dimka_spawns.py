import os
import re
import tkinter as tk
from tkinter import filedialog, ttk


# Функция для чтения данных из .dat файлов
def parse_dat_file(filepath):
    data = {}
    with open(filepath, "r") as file:
        for line in file:
            if line.strip():
                key, *value = line.strip().split()
                data[key] = " ".join(value) if value else None
    return data


# Функция для выбора папки
def select_folder(folder_label):
    folder = filedialog.askdirectory()
    if folder:
        folder_label.set(folder)


# Функция для обновления списка спавнов
def update_spawn_list():
    spawns_path = spawn_folder.get()

    if not spawns_path:
        tk.messagebox.showwarning("Ошибка", "Пожалуйста, выберите папку с спавнами!")
        return

    spawn_list.delete(0, tk.END)
    global spawns
    spawns = {}

    for root, _, files in os.walk(spawns_path):
        for file in files:
            if file.endswith(".dat"):
                filepath = os.path.join(root, file)
                data = parse_dat_file(filepath)
                spawn_id = int(data.get("ID", -1))
                if spawn_id != -1:
                    spawns[spawn_id] = {"data": data, "name": os.path.splitext(file)[0]}
                    spawn_list.insert(tk.END, f"ID {spawn_id}: {spawns[spawn_id]['name']}")


# Функция для отображения данных выбранного спавна
def display_spawn_details(event):
    selected_index = spawn_list.curselection()
    if not selected_index:
        return

    spawn_id = list(spawns.keys())[selected_index[0]]
    spawn_data = spawns[spawn_id]["data"]

    # Очистка таблицы
    tree.delete(*tree.get_children())

    # Сбор данных
    tables = []
    weights = []
    for key, value in spawn_data.items():
        if key.startswith("Table_") and ("_Spawn_ID" in key or "_Asset_ID" in key):
            table_index = int(re.search(r"Table_(\d+)_", key).group(1))
            if "_Spawn_ID" in key:
                tables.append((table_index, value, spawn_data.get(f"Table_{table_index}_Weight"), "spawn"))
            elif "_Asset_ID" in key:
                tables.append((table_index, value, spawn_data.get(f"Table_{table_index}_Weight"), "item"))

    total_weight = sum(int(w) for _, _, w, _ in tables if w)

    for table_index, table_id, weight, table_type in tables:
        weight_percent = int(weight) / total_weight * 100 if total_weight else 0
        linked_name = "Unknown"

        if table_type == "spawn" and int(table_id) in spawns:
            linked_name = spawns[int(table_id)]["name"]
        elif table_type == "item" and int(table_id) in items:
            linked_name = items[int(table_id)]["name"]

        tree.insert("", "end", values=(
            table_index, table_id, linked_name, f"{weight_percent:.2f}%", table_type
        ))


# Функция для отображения информации о вложенном спавне
def display_nested_spawn(table_id):
    nested_spawn_id = int(table_id)
    if nested_spawn_id not in spawns:
        tk.messagebox.showwarning("Ошибка", "Выбранный спавн не найден.")
        return

    nested_spawn_data = spawns[nested_spawn_id]["data"]

    nested_window = tk.Toplevel(root)
    nested_window.title(f"Детали вложенного спавна {spawns[nested_spawn_id]['name']}")

    columns_nested = ("table_index", "table_id", "linked_name", "weight_percent", "type")
    nested_tree = ttk.Treeview(nested_window, columns=columns_nested, show="headings", height=20)
    nested_tree.pack(fill=tk.BOTH, expand=True)

    for col in columns_nested:
        nested_tree.heading(col, text=col.replace("_", " ").capitalize())
        nested_tree.column(col, width=150)

    nested_tables = []
    total_weight_nested = 0
    for key, value in nested_spawn_data.items():
        if key.startswith("Table_") and ("_Spawn_ID" in key or "_Asset_ID" in key):
            table_index = int(re.search(r"Table_(\d+)_", key).group(1))
            if "_Spawn_ID" in key:
                nested_tables.append(
                    (table_index, value, nested_spawn_data.get(f"Table_{table_index}_Weight"), "spawn"))
            elif "_Asset_ID" in key:
                nested_tables.append((table_index, value, nested_spawn_data.get(f"Table_{table_index}_Weight"), "item"))

    total_weight_nested = sum(int(w) for _, _, w, _ in nested_tables if w)

    for table_index, table_id, weight, table_type in nested_tables:
        weight_percent_nested = int(weight) / total_weight_nested * 100 if total_weight_nested else 0
        linked_name_nested = "Unknown"

        if table_type == "spawn" and int(table_id) in spawns:
            linked_name_nested = spawns[int(table_id)]["name"]
        elif table_type == "item" and int(table_id) in items:
            linked_name_nested = items[int(table_id)]["name"]

        nested_tree.insert("", "end", values=(
            table_index, table_id, linked_name_nested, f"{weight_percent_nested:.2f}%", table_type
        ))


# Функция для загрузки предметов
def load_items():
    items_path = item_folder.get()

    if not items_path:
        tk.messagebox.showwarning("Ошибка", "Пожалуйста, выберите папку с предметами!")
        return

    global items
    items = {}

    for root, _, files in os.walk(items_path):
        for file in files:
            if file.endswith(".dat"):
                filepath = os.path.join(root, file)
                data = parse_dat_file(filepath)
                item_id = int(data.get("ID", -1))
                if item_id != -1:
                    items[item_id] = {"data": data, "name": os.path.splitext(file)[0]}


# Создание GUI
root = tk.Tk()
root.title("Spawn & Item Mapper")

# Выбор папок
frame = ttk.Frame(root, padding=10)
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# Папка Spawns
ttk.Label(frame, text="Папка Spawns:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
spawn_folder = tk.StringVar()
ttk.Entry(frame, textvariable=spawn_folder, width=50).grid(row=0, column=1, padx=5, pady=5)
ttk.Button(frame, text="Выбрать", command=lambda: select_folder(spawn_folder)).grid(row=0, column=2, padx=5, pady=5)
ttk.Button(frame, text="Обновить", command=update_spawn_list).grid(row=0, column=3, padx=5, pady=5)

# Папка Items
ttk.Label(frame, text="Папка Items:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
item_folder = tk.StringVar()
ttk.Entry(frame, textvariable=item_folder, width=50).grid(row=1, column=1, padx=5, pady=5)
ttk.Button(frame, text="Выбрать", command=lambda: select_folder(item_folder)).grid(row=1, column=2, padx=5, pady=5)
ttk.Button(frame, text="Загрузить", command=load_items).grid(row=1, column=3, padx=5, pady=5)

# Список спавнов
spawn_list_frame = ttk.LabelFrame(root, text="Список спавнов", padding=10)
spawn_list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
spawn_list = tk.Listbox(spawn_list_frame, height=20, width=50)
spawn_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
spawn_list.bind("<<ListboxSelect>>", display_spawn_details)

# Таблица деталей
details_frame = ttk.LabelFrame(root, text="Детали спавна", padding=10)
details_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
columns = ("table_index", "table_id", "linked_name", "weight_percent", "type")
tree = ttk.Treeview(details_frame, columns=columns, show="headings", height=20)
tree.pack(fill=tk.BOTH, expand=True)

for col in columns:
    tree.heading(col, text=col.replace("_", " ").capitalize())
    tree.column(col, width=150)


# Обработка двойного клика для отображения вложенного спавна
def on_double_click(event):
    item = tree.selection()
    if item:
        selected_item = tree.item(item, "values")
        table_type, table_id = selected_item[4], selected_item[1]
        if table_type == "spawn":
            display_nested_spawn(table_id)


tree.bind("<Double-1>", on_double_click)

root.mainloop()
