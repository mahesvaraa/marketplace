import asyncio
import logging
import math
import os
import random

import cv2
import numpy as np
from playwright.async_api import async_playwright

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
WINDOW_HEIGHT = 788
CENTER_X = WINDOW_WIDTH // 2
CENTER_Y = WINDOW_HEIGHT // 2
MOVE_DURATION = 0.01
MIN_DISTANCE = 30  # Уменьшил минимальное расстояние
MAX_DISTANCE = 400  # Добавил максимальное расстояние
GAME_URL = "https://wormax.io/?party=bot926"
TEMPLATES_DIR = "templates"
TEMPLATE_MATCH_THRESHOLD = 0.94  # Увеличил порог соответствия для более точного поиска


class GameObject:
    def __init__(self, name, location, shape):
        self.name = name
        self.x = int(location[0] + shape[1] // 2)
        self.y = int(location[1] + shape[0] // 2)
        self.distance = self.calculate_distance()
        self.shape = shape

    def calculate_distance(self):
        return math.sqrt((self.x - CENTER_X) ** 2 + (self.y - CENTER_Y) ** 2)

    def get_angle(self):
        return math.atan2(self.y - CENTER_Y, self.x - CENTER_X)

    def is_valid_target(self):
        # Проверяем, находится ли объект в допустимом диапазоне расстояний
        return MIN_DISTANCE <= self.distance <= MAX_DISTANCE


def load_templates():
    templates = {
        'food': {},
        'boosters': {},
        'enemies': {}
    }

    try:
        for filename in os.listdir(TEMPLATES_DIR):
            if not filename.endswith(".png"):
                continue

            path = os.path.join(TEMPLATES_DIR, filename)
            template = cv2.imread(path, cv2.IMREAD_COLOR)

            if template is None:
                logger.error(f"Не удалось загрузить шаблон: {filename}")
                continue

            if filename.startswith("food_"):
                templates['food'][filename] = template
            elif filename.startswith("booster_"):
                templates['boosters'][filename] = template
            elif filename.startswith("enemy_"):
                templates['enemies'][filename] = template

        logger.info(f"Загружены шаблоны: food={len(templates['food'])}, "
                    f"boosters={len(templates['boosters'])}, "
                    f"enemies={len(templates['enemies'])}")
    except Exception as e:
        logger.error(f"Ошибка при загрузке шаблонов: {e}")

    return templates


def find_objects(image, templates, threshold=TEMPLATE_MATCH_THRESHOLD):
    found_objects = []
    try:
        for category, category_templates in templates.items():
            for name, template in category_templates.items():
                result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= threshold)

                for loc in zip(*locations[::-1]):
                    obj = GameObject(name, loc, template.shape)
                   # if obj.is_valid_target():
                    found_objects.append(obj)
                    logger.debug(f"Найден объект {name} на расстоянии {obj.distance:.2f} пикселей")
    except Exception as e:
        logger.error(f"Ошибка при поиске объектов: {e}")

    return found_objects


def is_in_enemy_direction(target, enemies,
                          angle_threshold=math.pi / 3):  # Увеличил угол для более безопасного поведения
    if not enemies:
        return False

    target_angle = target.get_angle()

    for enemy in enemies:
        enemy_angle = enemy.get_angle()
        angle_diff = abs(target_angle - enemy_angle)

        if angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff

        if angle_diff < angle_threshold:
            return True

    return False


async def move_to_target(page, target):
    try:
        # Добавляем небольшое случайное отклонение для более естественного движения
        x = int(target.x + random.randint(-5, 5))
        y = int(target.y + random.randint(-5, 5))

        # Проверяем, что координаты не выходят за пределы окна
        x = max(0, min(x, WINDOW_WIDTH))
        y = max(0, min(y, WINDOW_HEIGHT))

        await page.mouse.click(x, y)
        await asyncio.sleep(MOVE_DURATION)
        return True
    except Exception as e:
        logger.error(f"Ошибка при движении к цели: {e}")
        return False


async def main():
    logger.info("Запуск скрипта...")
    templates = load_templates()
    last_target = None
    consecutive_failures = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[f'--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}', '--incognito']
        )

        page = await browser.new_page()
        await page.set_viewport_size({"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT})

        try:
            await page.goto(GAME_URL, timeout=60000)
            logger.info("Ожидание нажатия Space для старта...")

            await page.evaluate('''() => {
                window.spacePressed = false;
                window.addEventListener('keydown', (event) => {
                    if (event.code === 'Space') window.spacePressed = true;
                });
            }''')

            await page.wait_for_function('window.spacePressed === true', timeout=120000)
            logger.info("Начинаем игру...")

            while True:
                try:
                    # Делаем скриншот и ищем объекты
                    screenshot = await page.screenshot()
                    image = cv2.imdecode(np.frombuffer(screenshot, np.uint8), cv2.IMREAD_COLOR)
                    objects = find_objects(image, templates)

                    if objects:
                        # Разделяем объекты по категориям
                        enemies = [obj for obj in objects if obj.name.startswith("enemy_")]
                        boosters = [obj for obj in objects if obj.name.startswith("booster_")]
                        food = [obj for obj in objects if obj.name.startswith("food_")]

                        logger.info(f"Найдено объектов: еда={len(food)}, бустеры={len(boosters)}, враги={len(enemies)}")

                        target = None

                        # Сначала проверяем бустеры
                        if boosters:
                            safe_boosters = [b for b in boosters
                                             if not is_in_enemy_direction(b, enemies)]
                            if safe_boosters:
                                target = min(safe_boosters, key=lambda x: x.distance)

                        # Если нет безопасных бустеров, ищем безопасную еду
                        if not target and food:
                            safe_food = [f for f in food
                                         if not is_in_enemy_direction(f, enemies)]
                            if safe_food:
                                target = min(safe_food, key=lambda x: x.distance)

                        if target:
                            if target != last_target:
                                logger.info(f"Новая цель: {target.name} на расстоянии {target.distance:.2f} пикселей")
                                consecutive_failures = 0

                            success = await move_to_target(page, target)

                            if success:
                                last_target = target
                            else:
                                consecutive_failures += 1
                                if consecutive_failures >= 3:
                                    logger.info("Слишком много неудачных попыток, сброс цели")
                                    last_target = None
                                    consecutive_failures = 0

                        elif enemies:
                            # Убегаем от врагов
                            avg_enemy_angle = sum(e.get_angle() for e in enemies) / len(enemies)
                            escape_angle = avg_enemy_angle + math.pi

                            escape_distance = 200
                            escape_x = int(CENTER_X + escape_distance * math.cos(escape_angle))
                            escape_y = int(CENTER_Y + escape_distance * math.sin(escape_angle))

                            escape_target = GameObject("escape", (escape_x, escape_y), (0, 0))
                            await move_to_target(page, escape_target)
                            last_target = None

                    await asyncio.sleep(3)

                except Exception as e:
                    logger.error(f"Ошибка в игровом цикле: {e}")
                    await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            await browser.close()
            logger.info("Браузер закрыт.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
    finally:
        input("Нажмите Enter для выхода...")
