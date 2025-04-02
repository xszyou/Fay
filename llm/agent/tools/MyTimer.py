import abc
import sqlite3
import re
from typing import Any
from langchain.tools import BaseTool

class MyTimer(BaseTool, abc.ABC):
    name: str = "MyTimer"
    description: str = ("用于设置日程。接受3个参数，格式为: HH:MM|YYYYYYY|事项内容，所用标点符号必须为标准的英文字符。"
                   "其中，'HH:MM' 表示时间（24小时制），'YYYYYYY' 表示循环规则（每位代表一天，从星期一至星期日，1为循环，0为不循环，"
                   "如'1000100'代表每周一和周五循环），'事项内容' 是提醒的具体内容。返回例子：15:15|0000000|提醒主人叫咖啡")
    uid: int = 0

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 用例中没有用到 arun 不予具体实现
        pass

    def _run(self, para: str) -> str:
        # 拆分输入字符串
        parts = para.split("|")
        if len(parts) != 3:
            return f"输入格式错误，当前字符串{para} len:{len(parts)}。请按照 HH:MM|YYYYYYY|事项内容 格式提供参数，如：15:15|0000001|提醒主人叫咖啡。"
        
        time = parts[0].strip("'")
        repeat_rule = parts[1].strip("'")
        content = parts[2].strip("'")

        # 验证时间格式
        if not re.match(r'^[0-2][0-9]:[0-5][0-9]$', time):
            return "时间格式错误。请按照'HH:MM'格式提供时间。"

        # 验证循环规则格式
        if not re.match(r'^[01]{7}$', repeat_rule):
            return "循环规则格式错误。请提供长度为7的0和1组成的字符串。"

        # 验证事项内容
        if not isinstance(content, str) or not content:
            return "事项内容必须为非空字符串。"

        # 数据库操作
        conn = sqlite3.connect('memory/timer.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO timer (time, repeat_rule, content, uid) VALUES (?, ?, ?, ?)", (time, repeat_rule, content, self.uid))
            conn.commit()
        except sqlite3.Error as e:
            return f"数据库错误: {e}"
        finally:
            conn.close()

        return "日程设置成功"

if __name__ == "__main__":
    my_timer = MyTimer()
    result = my_timer._run("15:15|0000001|提醒主人叫咖啡")
    print(result)
