
#获取传感器状态        
def get_latest_list():
    info ="""
            {'result': True, 'code': 1, 'msg': '查询成功', 'data': {'co2': [{'ts': '2023-12-18 16:07:28.124', 'val': 8, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'S36', 'sensorid': 297}], 'air': [{'ts': '2023-12-18 16:07:28.124', 'val': 15, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'S37', 'sensorid': 298}], 'humidity': [{'ts': '2023-12-18 16:06:20.152', 'val': 49.7, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'MP14', 'sensorid': 302}, {'ts': '2023-12-18 16:06:57.861', 'val': 40.8, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'MP21', 'sensorid': 300}, {'ts': '2023-12-18 16:07:28.124', 'val': 99.41003, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'S34', 'sensorid': 299}], 'light': [{'ts': '2023-12-18 16:07:28.124', 'val': 185, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'bh1', 'sensorid': 301}], 'nh3': [{'ts': '2023-12-18 16:07:28.124', 'val': 14, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'S37', 'sensorid': 303}], 'temperature': [{'ts': '2023-12-18 16:03:58.326', 'val': 18.6, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'MP14', 'sensorid': 304}, {'ts': '2023-12-18 16:07:28.124', 'val': 22.9, 'istext': False, 'content_des': '', 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'port': 'MP21', 'sensorid': 305}]}}
          """
    return info

#获取开关状态
def get_switch_info():
    info = """
            [{'id': 16, 'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'onoff1': '1', 'onoff2': '0', 'onoff3': '0', 'onoff4': '0', 'onoff5': '0', 'onoff6': '1', 'onoff7': '1', 'onoff8': '0', 'onoff9': '0', 'onoff10': '0', 'onoff11': '0', 'onoff12': '0', 'onoff13': '0', 'onoff14': '0', 'onoff15': '0', 'onoff16': '0', 'updatetime': 1702886988874}]
            """
    return info

#设备开关操作
def do_switch_operation(num,onoff):
    return True

#获取传感器基本信息
def get_building_unit():
    info = """
            {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'lat': '0.0000000000000', 'lng': '0.0000000000000', 'sensor': [{'id': 297, 'title': '二氧化碳传感器', 'label': 'co2'}, {'id': 298, 'title': '空气质量传感器', 'label': 'air'}, {'id': 299, 'title': '土壤湿度传感器', 'label': 'humidity'}, {'id': 300, 'title': '温湿度传感器', 'label': 'humidity'}, {'id': 301, 'title': '光照传感器', 'label': 'light'}, {'id': 302, 'title': '温湿度传感器', 'label': 'humidity'}, {'id': 303, 'title': '氨气传感器', 'label': 'nh3'}, {'id': 304, 'title': '温湿度传感器', 'label': 'temperature'}, {'id': 305, 'title': '温湿度传感器', 'label': 'temperature'}], 'isonline': 1
            """
    return info

#获取开关记录日志
def get_switch_log():
    info = """
            [{'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 3, 'status': 0, 'createTime': 1702732876735, 'timetText': '2023-12-16 21:21:16'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 1, 'status': 1, 'createTime': 1702667478198, 'timetText': '2023-12-16 03:11:18'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 7, 'status': 1, 'createTime': 1702664989048, 'timetText': '2023-12-16 02:29:49'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 7, 'status': 0, 'createTime': 1702657012799, 'timetText': '2023-12-16 00:16:52'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 7, 'status': 1, 'createTime': 1702648220859, 'timetText': '2023-12-15 21:50:20'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 3, 'status': 1, 'createTime': 1702646816090, 'timetText': '2023-12-15 21:26:56'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 3, 'status': 0, 'createTime': 1702646531391, 'timetText': '2023-12-15 21:22:11'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 1, 'status': 0, 'createTime': 1702646530372, 'timetText': '2023-12-15 21:22:10'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 3, 'status': 1, 'createTime': 1702645992974, 'timetText': '2023-12-15 21:13:12'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 1, 'status': 1, 'createTime': 1702644950252, 'timetText': '2023-12-15 20:55:50'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 1, 'status': 0, 'createTime': 1702644949600, 'timetText': '2023-12-15 20:55:49'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 1, 'createTime': 1702634257442, 'timetText': '2023-12-15 17:57:37'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 0, 'createTime': 1702633183083, 'timetText': '2023-12-15 17:39:43'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 1, 'createTime': 1702631382970, 'timetText': '2023-12-15 17:09:42'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 0, 'createTime': 1702629480618, 'timetText': '2023-12-15 16:38:00'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 1, 'createTime': 1702628371951, 'timetText': '2023-12-15 16:19:31'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 0, 'createTime': 1702626695422, 'timetText': '2023-12-15 15:51:35'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 1, 'createTime': 1702625360795, 'timetText': '2023-12-15 15:29:20'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 0, 'createTime': 1702624152081, 'timetText': '2023-12-15 15:09:12'}, {'did': 'bbb14d38-2814-11ed-b20a-e45f019833ac', 'number': 6, 'status': 1, 'createTime': 1702622351970, 'timetText': '2023-12-15 14:39:11'}]
        """
    return info

#获取联动规则
def get_on_run_linkage():
    info = """
            {'result': True, 'code': 1, 'msg': '获取成功', 'data': [{'port': 'S34', 'sensorTitle': '土壤湿度传感器', 'label': 'humidity', 'minVal': 0, 'maxVal': 70, 'taskId': 'linkage_135', 'onoff': 1, 'switchNum': 4, 'keeptime': '0.25', 'delaytime': 30}, {'port': 'S36', 'sensorTitle': '二氧化碳传感器', 'label': 'co2', 'minVal': 0, 'maxVal': 8, 'taskId': 'linkage_138', 'onoff': 1, 'switchNum': 7, 'keeptime': '30.00', 'delaytime': 0}, {'port': 'MP14', 'sensorTitle': '温湿度传感器', 'label': 'temperature', 'minVal': 0, 'maxVal': 28, 'taskId': 'linkage_143', 'onoff': 1, 'switchNum': 1, 'keeptime': '0.00', 'delaytime': 0}, {'port': 'MP14', 'sensorTitle': '温湿度传感器', 'label': 
'temperature', 'minVal': 30, 'maxVal': 999999, 'taskId': 'linkage_144', 'onoff': 0, 'switchNum': 1, 'keeptime': '0.00', 'delaytime': 0}, {'port': 'MP14', 'sensorTitle': '温湿度传感器', 'label': 'temperature', 'minVal': 30, 'maxVal': 999999, 'taskId': 'linkage_145', 'onoff': 0, 'switchNum': 1, 'keeptime': '0.00', 'delaytime': 0}, {'port': 'bh1', 'sensorTitle': '光照传感器', 'label': 'light', 'minVal': 0, 'maxVal': 100, 'taskId': 'linkage_147', 'onoff': 1, 'switchNum': 6, 'keeptime': '30.00', 'delaytime': 50}]}
[{'port': 'S34', 'sensorTitle': '土壤湿度传感器', 'label': 'humidity', 'minVal': 0, 'maxVal': 70, 'taskId': 'linkage_135', 'onoff': 1, 'switchNum': 4, 'keeptime': '0.25', 'delaytime': 30}, {'port': 'S36', 'sensorTitle': '二氧化碳传感器', 'label': 'co2', 'minVal': 0, 'maxVal': 8, 'taskId': 'linkage_138', 'onoff': 1, 'switchNum': 7, 'keeptime': '30.00', 'delaytime': 0}, {'port': 'MP14', 'sensorTitle': '温湿度传感器', 'label': 'temperature', 'minVal': 0, 'maxVal': 28, 'taskId': 'linkage_143', 'onoff': 
1, 'switchNum': 1, 'keeptime': '0.00', 'delaytime': 0}, {'port': 'MP14', 'sensorTitle': '温湿度传感器', 'label': 'temperature', 'minVal': 30, 'maxVal': 999999, 'taskId': 'linkage_144', 'onoff': 0, 'switchNum': 1, 'keeptime': '0.00', 'delaytime': 0}, {'port': 'MP14', 'sensorTitle': '温湿度传感器', 'label': 'temperature', 'minVal': 30, 
'maxVal': 999999, 'taskId': 'linkage_145', 'onoff': 0, 'switchNum': 1, 'keeptime': '0.00', 'delaytime': 0}, {'port': 'bh1', 'sensorTitle': '光照传感器', 'label': 'light', 'minVal': 0, 'maxVal': 100, 'taskId': 'linkage_147', 'onoff': 1, 'switchNum': 6, 'keeptime': '30.00', 'delaytime': 50}]
            """
    return info

if __name__ == "__main__":
    str = get_on_run_linkage()
    print(str)