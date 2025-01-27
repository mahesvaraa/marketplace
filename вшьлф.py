import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import graphviz

# Тёмная тема для интерфейса
DARK_THEME = {
    "bg": "#1E1E1E",
    "fg": "#00FF7F",
    "text_bg": "#2D2D2D",
    "text_fg": "#00FF7F",
    "tree_bg": "#2D2D2D",
    "tree_fg": "#00FF7F",
    "button_bg": "#3C3C3C",
    "button_fg": "#00FF7F",
    "combo_bg": "#2D2D2D",
    "combo_fg": "#00FF7F"
}

def find_dat_files(directory):
    dat_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".dat"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory)
                dat_files.append((full_path, rel_path))
    return dat_files

def parse_dat_file(file_path):
    data = {}
    with open(file_path, "r") as file:
        for line in file:
            line = line.strip()
            if line:
                key, *value = line.split()
                data[key] = " ".join(value)
    return data

class SpawnEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Unturned Spawn Editor")
        self.root.geometry("1200x800")
        self.root.configure(bg=DARK_THEME["bg"])

        self.current_file_path = None
        self.current_data = {}
        self.spawn_directories = []

        # Создаем левую панель для дерева файлов
        self.tree_frame = tk.Frame(self.root, bg=DARK_THEME["bg"])
        self.tree_frame.pack(expand=True, fill="both", side="left", padx=5, pady=5)

        # Фрейм для управления директориями
        self.dirs_frame = tk.Frame(self.tree_frame, bg=DARK_THEME["bg"])
        self.dirs_frame.pack(fill="x", pady=5)

        # Кнопки управления директориями
        self.add_dir_button = tk.Button(
            self.dirs_frame,
            text="Добавить директорию",
            command=self.add_directory,
            bg=DARK_THEME["button_bg"],
            fg=DARK_THEME["button_fg"]
        )
        self.add_dir_button.pack(side="left", padx=5)

        self.remove_dir_button = tk.Button(
            self.dirs_frame,
            text="Удалить директорию",
            command=self.remove_directory,
            bg=DARK_THEME["button_bg"],
            fg=DARK_THEME["button_fg"]
        )
        self.remove_dir_button.pack(side="left", padx=5)

        # Список директорий
        self.dirs_listbox = tk.Listbox(
            self.tree_frame,
            bg=DARK_THEME["text_bg"],
            fg=DARK_THEME["text_fg"],
            selectmode=tk.SINGLE,
            height=3
        )
        self.dirs_listbox.pack(fill="x", pady=5)

        # Создаем Treeview с поддержкой иерархии
        self.tree = ttk.Treeview(self.tree_frame, show="tree")
        self.tree.heading("#0", text="Файлы .dat")
        self.tree.pack(expand=True, fill="both", side="left")

        # Добавляем ползунок прокрутки для Treeview
        self.tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree_scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=self.tree_scroll.set)

        # Настройка тёмной темы
        style = ttk.Style()
        style.configure("Treeview", background=DARK_THEME["tree_bg"], foreground=DARK_THEME["tree_fg"])
        style.configure("Treeview.Heading", background=DARK_THEME["button_bg"], foreground=DARK_THEME["button_fg"])

        # Правая панель для контента и управления весами
        self.right_panel = tk.Frame(self.root, bg=DARK_THEME["bg"])
        self.right_panel.pack(expand=True, fill="both", side="right", padx=5, pady=5)

        # Панель управления весами
        self.weights_frame = tk.Frame(self.right_panel, bg=DARK_THEME["bg"])
        self.weights_frame.pack(fill="x", pady=5)

        # Комбобокс для выбора веса
        self.weight_var = tk.StringVar()
        self.weight_combo = ttk.Combobox(self.weights_frame, textvariable=self.weight_var)
        self.weight_combo.pack(side="left", padx=5)

        # Поле для ввода нового значения веса
        self.weight_entry = tk.Entry(self.weights_frame, bg=DARK_THEME["text_bg"], fg=DARK_THEME["text_fg"])
        self.weight_entry.pack(side="left", padx=5)

        # Кнопка изменения веса
        self.update_weight_button = tk.Button(
            self.weights_frame,
            text="Изменить вес",
            command=self.update_weight,
            bg=DARK_THEME["button_bg"],
            fg=DARK_THEME["button_fg"]
        )
        self.update_weight_button.pack(side="left", padx=5)

        # Текстовое поле для содержимого файла
        self.text_area = tk.Text(
            self.right_panel,
            wrap="none",
            font=("Courier New", 12),
            bg=DARK_THEME["text_bg"],
            fg=DARK_THEME["text_fg"]
        )
        self.text_area.pack(expand=True, fill="both", pady=5)

        # Кнопки управления
        self.buttons_frame = tk.Frame(self.right_panel, bg=DARK_THEME["bg"])
        self.buttons_frame.pack(fill="x", pady=5)

        # Кнопки управления файлами
        buttons = [
            ("Сохранить", self.save_file),
            ("Показать зависимости", self.show_dependencies),
            ("Добавить предмет", self.add_item)
        ]

        for text, command in buttons:
            btn = tk.Button(
                self.buttons_frame,
                text=text,
                command=command,
                bg=DARK_THEME["button_bg"],
                fg=DARK_THEME["button_fg"]
            )
            btn.pack(side="left", padx=5)

        # Привязываем обработчик выбора файла
        self.tree.bind("<<TreeviewSelect>>", self.on_file_select)

        # Пытаемся найти стандартную папку spawns
        self.try_find_spawns_folder()

    def try_find_spawns_folder(self):
        default_paths = [
            r"E:\UNTURNED_SERVER\my_server\Bundles\Spawns"
        ]

        found = False
        for path in default_paths:
            if os.path.exists(path):
                self.spawn_directories.append(path)
                self.dirs_listbox.insert(tk.END, path)
                found = True

        if not found:
            messagebox.showinfo(
                "Папка не найдена",
                "Стандартная папка spawns не найдена. Используйте кнопку 'Добавить директорию' для выбора папок вручную."
            )

        self.reload_file_tree()

    def add_directory(self):
        directory = filedialog.askdirectory(title="Выберите директорию spawns")
        if directory:
            if directory not in self.spawn_directories:
                self.spawn_directories.append(directory)
                self.dirs_listbox.insert(tk.END, directory)
                self.reload_file_tree()

    def remove_directory(self):
        selection = self.dirs_listbox.curselection()
        if selection:
            index = selection[0]
            directory = self.spawn_directories[index]
            self.spawn_directories.pop(index)
            self.dirs_listbox.delete(index)
            self.reload_file_tree()

    def reload_file_tree(self):
        # Clear existing tree and nodes dictionary
        self.tree.delete(*self.tree.get_children())
        self.nodes = {}

        for directory in self.spawn_directories:
            # Create root node for directory
            dir_name = os.path.basename(directory)
            dir_node = self.tree.insert("", "end", text=dir_name, values=(directory,))

            # Find all .dat files in the directory
            dat_files = find_dat_files(directory)

            for full_path, rel_path in dat_files:
                # Split the relative path into parts
                path_parts = rel_path.split(os.sep)
                current_parent = dir_node
                current_path = ""

                # Create nodes for each subdirectory level
                for i, part in enumerate(path_parts[:-1]):  # Exclude the file name
                    current_path = os.path.join(current_path, part) if current_path else part
                    node_id = f"{directory}:{current_path}"

                    # Check if this node already exists
                    if node_id not in self.nodes:
                        # Create new node
                        self.nodes[node_id] = self.tree.insert(
                            current_parent,
                            "end",
                            text=part,
                            values=(os.path.join(directory, current_path),)
                        )
                    current_parent = self.nodes[node_id]

                # Finally, insert the file itself
                self.tree.insert(
                    current_parent,
                    "end",
                    text=path_parts[-1],
                    values=(full_path,)
                )

    def on_file_select(self, event):
        selected_item = self.tree.selection()[0]
        file_path = self.tree.item(selected_item)["values"][0]

        # Проверяем, что выбран файл, а не директория
        if file_path is not None and not os.path.isdir(file_path):
            self.current_file_path = file_path
            with open(file_path, "r") as file:
                content = file.read()
                self.text_area.delete(1.0, tk.END)
                self.text_area.insert(tk.END, content)
            self.update_weights_list()

    def update_weights_list(self):
        content = self.text_area.get(1.0, tk.END)
        lines = content.splitlines()
        weights = []

        for line in lines:
            if "Weight" in line:
                weights.append(line.strip())

        self.weight_combo['values'] = weights
        if weights:
            self.weight_combo.set(weights[0])

    def update_weight(self):
        if not self.weight_var.get():
            return

        try:
            new_weight = int(self.weight_entry.get())
            if new_weight < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Ошибка", "Введите корректное положительное число")
            return

        content = self.text_area.get(1.0, tk.END).splitlines()
        selected_weight = self.weight_var.get()
        weight_name = selected_weight.split()[0]

        for i, line in enumerate(content):
            if line.startswith(weight_name):
                content[i] = f"{weight_name} {new_weight}"
                break

        self.text_area.delete(1.0, tk.END)
        self.text_area.insert(tk.END, "\n".join(content))
        self.update_weights_list()

    def save_file(self):
        if self.current_file_path:
            with open(self.current_file_path, "w") as file:
                file.write(self.text_area.get(1.0, tk.END))
            messagebox.showinfo("Сохранено", "Файл успешно сохранен!")

    def show_dependencies(self):
        if self.current_file_path:
            data = parse_dat_file(self.current_file_path)

            # Поиск всех связанных файлов через Asset_ID
            dependencies = {}
            for key, value in data.items():
                if key.startswith("Table_") and key.endswith("_Spawn_ID"):
                    dependencies[key] = value

            # Отображение зависимостей в текстовом поле
            self.text_area.insert(tk.END, "\n\nЗависимости:\n")
            for key, asset_id in dependencies.items():
                self.text_area.insert(tk.END, f"{key}: {asset_id}\n")

            # Визуализация зависимостей
            dot = graphviz.Digraph()
            for key, asset_id in dependencies.items():
                dot.edge(os.path.basename(self.current_file_path), asset_id)
            dot.render("dependencies.gv", view=True)

    def add_item(self):
        if self.current_file_path:
            item_id = simpledialog.askinteger("Добавить предмет", "Введите ID предмета:")
            if item_id:
                lines = self.text_area.get(1.0, tk.END).splitlines()
                tables = [line for line in lines if line.startswith("Tables")]
                if tables:
                    table_count = int(tables[0].split()[-1])
                    lines.append(f"Table_{table_count}_Spawn_ID {item_id}")
                    lines.append(f"Table_{table_count}_Weight 10")  # Вес по умолчанию
                    lines[lines.index(tables[0])] = f"Tables {table_count + 1}"
                    self.text_area.delete(1.0, tk.END)
                    self.text_area.insert(tk.END, "\n".join(lines))
                    self.update_weights_list()

if __name__ == "__main__":
    root = tk.Tk()
    editor = SpawnEditor(root)
    root.mainloop()