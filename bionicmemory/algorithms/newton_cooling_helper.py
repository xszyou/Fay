import math
from enum import Enum
from datetime import datetime

class CoolingRate(Enum):
    MINUTES_20 = (0.582, 20 * 60)
    HOURS_1 = (0.442, 1 * 60 * 60)
    HOURS_9 = (0.358, 9 * 60 * 60)
    DAYS_1 = (0.337, 1 * 24 * 60 * 60)
    DAYS_2 = (0.278, 2 * 24 * 60 * 60)
    DAYS_6 = (0.254, 6 * 24 * 60 * 60)
    DAYS_31 = (0.211, 31 * 24 * 60 * 60)

class NewtonCoolingHelper:
    @staticmethod
    def calculate_cooling_rate(enum_value: CoolingRate) -> float:
        """
        根据枚举值计算冷却速率系数（alpha）。
        """
        final_temperature_ratio, time_interval = enum_value.value
        return -math.log(final_temperature_ratio) / time_interval

    @staticmethod
    def calculate_newton_cooling_effect(initial_temperature: float, time_interval: float, cooling_rate: float = None) -> float:
        """
        根据牛顿冷却定律计算当前时间的温度。
        """
        if cooling_rate is None:
            cooling_rate = NewtonCoolingHelper.calculate_cooling_rate(CoolingRate.DAYS_31)
        return initial_temperature * math.exp(-cooling_rate * time_interval)

    @staticmethod
    def calculate_time_difference(update_time: datetime, current_time: datetime) -> float:
        """
        计算上次更新时间与当前时间之间的时间差。
        """
        if isinstance(update_time, str):
            update_time = datetime.fromisoformat(update_time)
        if isinstance(current_time, str):
            current_time = datetime.fromisoformat(current_time)
        time_delta = current_time - update_time
        return time_delta.total_seconds()
    
    @staticmethod
    def get_threshold(cooling_rate: CoolingRate=None) -> float:
        if cooling_rate is None:
            cooling_rate=CoolingRate.DAYS_31
        return cooling_rate.value[0]
