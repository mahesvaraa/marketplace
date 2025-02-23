from collections import deque, defaultdict
from typing import List, Any, Dict


class MarketChangesTracker:
    def __init__(self, history_size: int = 10):
        self.history_size = history_size
        self.changes_history = deque(maxlen=history_size)  # Хранит списки changes для последних N итераций

    def add_changes(self, changes: List[Dict[str, Any]], frequency=3) -> List[Dict[str, Any]]:
        """
        Добавляет новые изменения в историю и возвращает список item_id,
        которые появились больше двух раз за последние N итераций
        """
        self.changes_history.append(changes)

        # Подсчитываем частоту появления каждого item_id во всей истории
        item_frequency = defaultdict(int)
        for changes_list in self.changes_history:
            # Получаем уникальные item_id из текущего списка изменений
            unique_items = {change.item_id for change in changes_list}
            for item_id in unique_items:
                item_frequency[item_id] += 1

        # Находим item_id, которые появились больше двух раз
        frequent_items = [item_id for item_id, count in item_frequency.items() if count >= frequency]

        # Возвращаем изменения только для частых item_id
        return [change for change in changes if change["item_id"] in frequent_items]
