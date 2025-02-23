@echo off
chcp 65001
setlocal

:: Переход в папку со скриптами
cd /d "%~dp0market_seller"

:: Создаём виртуальное окружение, если его нет
if not exist venv (
    echo Создаю виртуальное окружение...
    python -m venv venv
)

:: Активируем виртуальное окружение
echo Активирую виртуальное окружение...
call venv\Scripts\activate

:: Устанавливаем зависимости, если есть requirements.txt
if exist requirements.txt (
    echo Устанавливаю зависимости...
    pip install -r requirements.txt
)

:: Запускаем main.py
echo Запускаю main.py...
python main.py

:: Оставляем окно открытым после завершения
cmd

