from playwright.async_api import async_playwright  # Используем асинхронный API
import cv2
import numpy as np
import logging
import os
import random
import time
import asyncio  # Добавляем asyncio для асинхронного выполнения

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("script.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Настройки
WINDOW_WIDTH = 989
WINDOW_HEIGHT = 788  # Увеличено на 15 пикселей (было 773)
CENTER_X = WINDOW_WIDTH // 2
CENTER_Y = WINDOW_HEIGHT // 2
TOLERANCE = 10
GAME_URL = "https://wormax.io/?party=bot92"
TEMPLATES_DIR = "templates"

# Загрузка шаблонов
def load_templates():
    templates = {}
    try:
        for filename in os.listdir(TEMPLATES_DIR):
            if filename.endswith(".png"):
                name = os.path.splitext(filename)[0]
                path = os.path.join(TEMPLATES_DIR, filename)
                template = cv2.imread(path, cv2.IMREAD_COLOR)
                if template is None:
                    logger.error(f"Не удалось загрузить шаблон: {filename}")
                    continue
                templates[name] = template
        logger.info(f"Загружены шаблоны: {list(templates.keys())}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке шаблонов: {e}")
    return templates

# Поиск объектов на изображении
import cv2

def find_objects(image, templates, threshold=0.3):
    results = {}
    try:
        for name, template in templates.items():
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val > threshold:
                h, w = template.shape[:2]
                top_left = max_loc
                bottom_right = (top_left[0] + w, top_left[1] + h)
                # Подсветить объект на изображении
                cv2.rectangle(image, top_left, bottom_right, (0, 255, 0), 2)
                results[name] = (max_loc, template.shape)
    except Exception as e:
        logger.error(f"Ошибка при поиске объектов: {e}")
    return image, results


# Функция для проверки, находится ли объект в центре
def is_object_in_center(target_x, target_y, center_x, center_y, tolerance=10):
    return abs(target_x - center_x) < tolerance and abs(target_y - center_y) < tolerance

# Функция для движения к цели
async def move_to_target(page, target_x, target_y):
    try:
        # Добавляем случайное отклонение
        offset_x = random.randint(-10, 10)
        offset_y = random.randint(-10, 10)
        target_x += offset_x
        target_y += offset_y

        # Добавляем случайную задержку
        delay = random.uniform(0.1, 0.5)
        await asyncio.sleep(delay)

        # Двигаем мышь к цели
        await page.mouse.move(target_x, target_y)
    except Exception as e:
        logger.error(f"Ошибка при движении к цели: {e}")

# Функция для проверки, находится ли точка на линии
def is_point_on_line(start_x, start_y, end_x, end_y, point_x, point_y, tolerance=10):
    """
    Проверяет, находится ли точка (point_x, point_y) на линии между (start_x, start_y) и (end_x, end_y).
    """
    # Вычисляем расстояние от точки до линии
    distance = abs((end_y - start_y) * point_x - (end_x - start_x) * point_y + end_x * start_y - end_y * start_x) / \
               ((end_y - start_y) ** 2 + (end_x - start_x) ** 2) ** 0.5

    # Если расстояние меньше допуска, точка находится на линии
    return distance < tolerance

# Функция для проверки, есть ли враг на пути
def is_enemy_on_path(image, templates, start_x, start_y, target_x, target_y, enemy_templates):
    """
    Проверяет, есть ли враг на пути от (start_x, start_y) до (target_x, target_y).
    """
    try:
        # Ищем врагов на изображении
        enemies = find_objects(image, enemy_templates)

        # Если враги найдены, проверяем, находятся ли они на пути
        for enemy_name, (enemy_location, enemy_shape) in enemies.items():
            enemy_x, enemy_y = enemy_location
            enemy_w, enemy_h = enemy_shape[1], enemy_shape[0]
            enemy_center_x = enemy_x + enemy_w // 2
            enemy_center_y = enemy_y + enemy_h // 2

            # Проверяем, находится ли враг на линии между начальной и целевой точкой
            if is_point_on_line(start_x, start_y, target_x, target_y, enemy_center_x, enemy_center_y, tolerance=20):
                logger.info(f"Враг {enemy_name} на пути к цели.")
                return True

        # Если врагов на пути нет
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке врагов на пути: {e}")
        return False

# Функция для нажатия на кнопки
async def click_buttons(page, objects):
    try:
        # Последовательно ищем и нажимаем на кнопки
        for button_name in ["Knopka_1", "Knopka_2", "Knopka_3"]:
            if button_name in objects:
                location, shape = objects[button_name]
                x, y = location
                w, h = shape[1], shape[0]
                center_x = x + w // 2
                center_y = y + h // 2
                logger.info(f"Найдена кнопка {button_name} на координатах: ({center_x}, {center_y})")
                await move_to_target(page, center_x, center_y)
                await page.mouse.click(center_x, center_y)
                logger.info(f"Нажата кнопка {button_name}.")
                await asyncio.sleep(1)  # Пауза между нажатиями
    except Exception as e:
        logger.error(f"Ошибка при нажатии на кнопки: {e}")

# Функция для циклического зажатия клавиши Q
async def q_key_cycle(page):
    try:
        while True:
            # Зажимаем Q на 10 секунд
            await page.keyboard.down('Q')
            logger.info("Клавиша Q зажата для ускорения.")
            await asyncio.sleep(10)

            # Отпускаем Q на 0.5 секунды
            await page.keyboard.up('Q')
            await asyncio.sleep(0.5)

            # Зажимаем Q на 15 секунд
            await page.keyboard.down('Q')
            logger.info("Клавиша Q зажата для ускорения.")
            await asyncio.sleep(15)

            # Отпускаем Q
            await page.keyboard.up('Q')
    except Exception as e:
        logger.error(f"Ошибка в цикле зажатия клавиши Q: {e}")

# Основной скрипт
async def main():
    logger.info("Запуск скрипта...")

    # Загружаем шаблоны
    templates = load_templates()
    enemy_templates = {name: template for name, template in templates.items() if name.startswith("enemy")}

    async with async_playwright() as p:
        # Запуск браузера
        browser = await p.chromium.launch(
            headless=False,
            args=[
                f'--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}',
                '--incognito',
                '--disable-blink-features=AutomationControlled'  # Отключаем флаги автоматизации
            ]
        )
        page = await browser.new_page()
        await page.set_viewport_size({"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT})

        try:
            # Открываем игру
            await page.goto(GAME_URL, timeout=60000)
            logger.info(f"Открыта страница: {GAME_URL}")
            logger.info("Ожидание нажатия Space для старта...")

            # Ждём загрузки игры
            await asyncio.sleep(10)  # Подождите 10 секунд перед проверкой Space

            # Добавляем обработчик события нажатия Space
            await page.evaluate('''() => {
                window.spacePressed = false;
                window.addEventListener('keydown', (event) => {
                    if (event.code === 'Space') {
                        window.spacePressed = true;
                    }
                });
            }''')

            # Ждём нажатия Space
            await page.wait_for_function('window.spacePressed === true', timeout=120000)
            logger.info("Space нажата. Начинаем работу...")

            # Задержка перед началом зажатия клавиши Q
            await asyncio.sleep(10)
            logger.info("Начинаем цикл зажатия клавиши Q.")

            # Запускаем цикл зажатия клавиши Q в отдельной задаче
            asyncio.create_task(q_key_cycle(page))

            # Флаг для отслеживания движения к цели
            is_moving_to_target = False
            current_target = None  # Текущая цель (еда или бустер)

            # Основной цикл игры
            while True:
                try:
                    # Делаем скриншот
                    screenshot = await page.screenshot()
                    image = cv2.imdecode(np.frombuffer(screenshot, np.uint8), cv2.IMREAD_COLOR)

                    # Если не движемся к цели, ищем новую цель
                    if not is_moving_to_target:
                        objects = find_objects(image, templates)

                        # Нажимаем на кнопки Knopka_1, Knopka_2, Knopka_3
                        await click_buttons(page, objects)

                        # Приоритет бустеров
                        boosters = {name: loc_shape for name, loc_shape in objects.items() if name.startswith("booster")}
                        foods = {name: loc_shape for name, loc_shape in objects.items() if name.startswith("food")}

                        # Обрабатываем бустеры
                        if boosters:
                            for name, (location, shape) in boosters.items():
                                x, y = location
                                w, h = shape[1], shape[0]
                                center_x = x + w // 2
                                center_y = y + h // 2

                                # Проверяем, есть ли враг на пути
                                if not is_enemy_on_path(image, templates, CENTER_X, CENTER_Y, center_x, center_y, enemy_templates):
                                    logger.info(f"Найден бустер: {name} на координатах: ({center_x}, {center_y})")
                                    current_target = (center_x, center_y)
                                    is_moving_to_target = True
                                    await move_to_target(page, center_x, center_y)
                                    break  # Переходим к следующему бустеру

                        # Обрабатываем еду, если нет бустеров
                        elif foods:
                            for name, (location, shape) in foods.items():
                                x, y = location
                                w, h = shape[1], shape[0]
                                center_x = x + w // 2
                                center_y = y + h // 2

                                # Проверяем, есть ли враг на пути
                                if not is_enemy_on_path(image, templates, CENTER_X, CENTER_Y, center_x, center_y, enemy_templates):
                                    logger.info(f"Найдена еда: {name} на координатах: ({center_x}, {center_y})")
                                    current_target = (center_x, center_y)
                                    is_moving_to_target = True
                                    await move_to_target(page, center_x, center_y)
                                    break  # Переходим к следующей еде

                    # Если движемся к цели, проверяем, достигнута ли она
                    if is_moving_to_target and current_target:
                        target_x, target_y = current_target
                        if is_object_in_center(target_x, target_y, CENTER_X, CENTER_Y, TOLERANCE):
                            logger.info(f"Цель достигнута: ({target_x}, {target_y})")
                            is_moving_to_target = False
                            current_target = None

                except Exception as e:
                    logger.error(f"Ошибка в основном цикле: {e}")

                # Пауза между итерациями
                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Ошибка в основном блоке: {e}")

        finally:
            # Отпускаем клавишу Q и закрываем браузер
            await page.keyboard.up('Q')
            await browser.close()
            logger.info("Браузер закрыт.")

# Запуск скрипта
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка в основном блоке: {e}")
    finally:
        input("Нажмите Enter для выхода...")  # Ожидание ввода, чтобы консоль не закрывалась