import os
from typing import Any

import requests
from langchain.tools import BaseTool
import time
import agent.tools.IotmService as IotmService
from datetime import datetime

class CheckSensor(BaseTool):
    name = "CheckSensor"
    description = "此工具用于查询农业箱在线状态、传感器数据、设备开关状态"

    def __init__(self):
        super().__init__()

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass


    def _run(self, para: str) -> str:
        #箱子信息
        building_infos = IotmService.get_building_unit()
        is_online = building_infos.get('isonline', 0)
        #传感器数据
        sensor_all_infos = IotmService.get_latest_list()
        sensor_infos = sensor_all_infos['data']
        desc_list = {
        'temperature': '温度',
        'humidity': '湿度',
        'co2': '二氧化碳',
        'light': '箱内的光照强度的值，当箱内光照强度太低时，生长灯会被打开，传感器位置是可以检测到生长灯的亮度的',
        'air': '污染气体',
        'nh3': '氨气'
        }

        infos = []
        for sensor_type, sensor_data in sensor_infos.items():
                for data_point in sensor_data:
                        if sensor_type == 'temperature':
                             if data_point['port'] == 'MP14':
                                  description = '箱外温度'
                             else:
                                  description = '箱内温度' 

                        elif sensor_type == 'humidity':
                             if data_point['port'] == 'MP14':
                                  description = '箱外湿度'
                             elif data_point['port'] == 'S34':
                                  description = '箱内土壤的湿度，检测的数所有延迟，水在土壤里有个渗透的过程'
                             else:
                                  description = '箱内湿度' 
                        else:
                                description = desc_list.get(sensor_type, 'Unknown')  # Get description from desc_list, default to 'Unknown'
                        timestamp = data_point['ts']
                        value = data_point['val']
                        infos.append({'ts': timestamp, 'val': value, 'desc':description })            
        #开关数据
        switch_all_infos = IotmService.get_switch_info()
        switch_infos = {}
        switch_dict = switch_all_infos[0]
        #设备配置
        switch_infos['小风扇'] = 'on' if switch_dict.get('onoff1', '') == '1' else 'off'
        switch_infos['电热风扇'] = 'on' if switch_dict.get('onoff2', '') == '1' else 'off'
        switch_infos['制冷风扇'] = 'on' if switch_dict.get('onoff3', '') == '1' else 'off'
        switch_infos['水开关'] = 'on' if switch_dict.get('onoff4', '') == '1' else 'off'
        switch_infos['肥料开关'] = 'on' if switch_dict.get('onoff5', '') == '1' else 'off'
        switch_infos['植物生长灯'] = 'on' if switch_dict.get('onoff6', '') == '1' else 'off'
        switch_infos['二氧化碳'] = 'on' if switch_dict.get('onoff7', '') == '1' else 'off'
        current_time = datetime.now()
        current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")
        result = {'sensor_infos': infos, 'switch_infos': switch_infos, 'is_online': is_online, 'ts' : current_time_str} 
        return result

if __name__ == "__main__":
    tool = CheckSensor()
    info = tool.run("")
    print(info)
