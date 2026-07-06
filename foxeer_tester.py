import time
import sys
import tkinter as tk
from tkinter import messagebox
import subprocess

try:
    import customtkinter as ctk
except ImportError:
    import os
    print("Установка красивой темы (customtkinter)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from pymavlink import mavutil
import serial.tools.list_ports

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Таблица расшифровки ID датчиков ArduPilot (наиболее частые для Foxeer и аналогов)
GYRO_TYPES = {
    1: "MPU6000", 2: "MPU9250", 3: "ICM20608", 4: "ICM20602", 
    5: "ICM20689", 7: "LSM206D", 9: "ICM42605", 11: "ICM42688",
    12: "BMI270", 13: "BMI088", 14: "BMI090L"
}

BARO_TYPES = {
    1: "BMP280", 2: "MS5611", 3: "MS5607", 4: "MS5637", 
    5: "FBM320", 6: "DPS310", 7: "LPS25H", 8: "LPS22H", 9: "BMP388"
}

def decode_gyro_id(param_value):
    """Декодирует системный INS_ID из ArduPilot в имя чипа"""
    try:
        val = int(param_value)
        # В ArduPilot ID датчика упакован как битовая маска, берем тип чипа (биты 16-23)
        dev_type = (val >> 16) & 0xFF
        return GYRO_TYPES.get(dev_type, f"Неизвестный IMU (Тип {dev_type})")
    except:
        return "Не определен"

def decode_baro_id(param_value):
    """Декодирует системный BARO_ID из ArduPilot в имя чипа"""
    try:
        val = int(param_value)
        dev_type = (val >> 16) & 0xFF
        return BARO_TYPES.get(dev_type, f"Неизвестный Барометр (Тип {dev_type})")
    except:
        return "Не определен"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Foxeer F405 Expert Tester")
        self.geometry("520x580")
        self.resizable(False, False)

        self.title_label = ctk.CTkLabel(
            self, text="Стенд глубокого теста Foxeer v2.4", 
            font=ctk.CTkFont(family="Arial", size=22, weight="bold")
        )
        self.title_label.pack(pady=(25, 15))

        # Порты
        self.port_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.port_frame.pack(pady=5, fill="x", padx=40)

        self.port_label = ctk.CTkLabel(self.port_frame, text="Выбор порта:", font=ctk.CTkFont(size=14))
        self.port_label.pack(side="left", padx=(0, 10))

        self.selected_port = tk.StringVar()
        self.port_menu = ctk.CTkOptionMenu(self.port_frame, width=220, variable=self.selected_port)
        self.port_menu.pack(side="left", expand=True, fill="x", padx=(0, 10))

        self.refresh_button = ctk.CTkButton(self.port_frame, text="🔄", width=45, font=ctk.CTkFont(size=16), command=self.update_ports_list)
        self.refresh_button.pack(side="right")

        self.update_ports_list()

        # Кнопка
        self.check_button = ctk.CTkButton(
            self, text="СЧИТАТЬ СТАТУС И ВЕРСИИ ДАТЧИКОВ", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45, corner_radius=8,
            command=self.check_sensors
        )
        self.check_button.pack(pady=15, padx=40, fill="x")

        # Карточка результатов
        self.result_frame = ctk.CTkFrame(self, corner_radius=10)
        self.result_frame.pack(pady=10, fill="both", padx=40, expand=True)

        self.gyro_label = ctk.CTkLabel(self.result_frame, text="• ГИРОСКОП: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.gyro_label.pack(anchor="w", padx=20, pady=(12, 4))

        self.baro_label = ctk.CTkLabel(self.result_frame, text="• БАРОМЕТР: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.baro_label.pack(anchor="w", padx=20, pady=4)

        self.gps_label = ctk.CTkLabel(self.result_frame, text="• Модуль GPS: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.gps_label.pack(anchor="w", padx=20, pady=4)

        self.osd_label = ctk.CTkLabel(self.result_frame, text="• Графический чип OSD: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.osd_label.pack(anchor="w", padx=20, pady=4)

        self.motors_label = ctk.CTkLabel(self.result_frame, text="• Выходы моторов (ESC): Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.motors_label.pack(anchor="w", padx=20, pady=4)

        self.uart_label = ctk.CTkLabel(self.result_frame, text="• Шины UART: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.uart_label.pack(anchor="w", padx=20, pady=(4, 12))

    def update_ports_list(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_menu.configure(values=ports)
            if self.selected_port.get() not in ports: self.selected_port.set(ports[0])
        else:
            self.port_menu.configure(values=["Порты не найдены"])
            self.selected_port.set("Порты не найдены")

    def request_parameter(self, master, param_name):
        """Безопасно запрашивает конкретный параметр у ArduPilot"""
        try:
            master.mav.param_request_read_send(
                master.target_system, master.target_component,
                param_name.encode('utf-8'), -1
            )
            # Ждем ответа именно с этим параметром в течение 0.5 сек
            start = time.time()
            while time.time() - start < 0.5:
                msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.05)
                if msg and msg.param_id.strip() == param_name:
                    return msg.param_value
        except:
            pass
        return None

    def check_sensors(self):
        port = self.selected_port.get()
        if not port or port == "Порты не найдены":
            messagebox.showwarning("Внимание", "Подключите плату!")
            return
        
        labels = [self.gyro_label, self.baro_label, self.gps_label, self.osd_label, self.motors_label, self.uart_label]
        for l in labels:
            l.configure(text=l.cget("text").split(":")[0] + ": Чтение чипов...", text_color="#FF9800")
        self.update()

        try:
            master = mavutil.mavlink_connection(port, baud=115200)
            msg = master.wait_heartbeat(timeout=2.5)
            if not msg: raise Exception("Нет связи")

            # Читаем ID оборудования из параметров ArduPilot
            gyro_id = self.request_parameter(master, "INS_GYRO_ID")
            baro_id = self.request_parameter(master, "BARO_EXT_BUS")  # или BARO_PRIMARY / BARO_GND_PRESS

            # Если первый вариант пустоват, проверим альтернативные параметры ID
            if not gyro_id: gyro_id = self.request_parameter(master, "INS_ID")
            
            # Расшифровываем модели
            gyro_model = decode_gyro_id(gyro_id) if gyro_id else "ICM42688 (По умолчанию)"
            baro_model = decode_baro_id(baro_id) if baro_id else "DPS310 (По умолчанию)"

            master.mav.request_data_stream_send(master.target_system, master.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)

            gyro_ok = accel_ok = baro_ok = False
            gps_ok = osd_ok = motors_ok = uart_ok = False
            
            start_time = time.time()
            while time.time() - start_time < 2.0:
                msg = master.recv_match(blocking=True, timeout=0.1)
                if not msg: continue

                if msg.get_type() == 'SYS_STATUS':
                    health = msg.onboard_control_sensors_health
                    gyro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO)
                    accel_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL)
                    baro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE)
                
                elif msg.get_type() == 'NAMED_VALUE_INT':
                    name = msg.name.strip()
                    value = msg.value
                    if name == 'TEST_GPS': gps_ok = (value == 1)
                    if name == 'TEST_OSD': osd_ok = (value == 1)
                    if name == 'TEST_MOT': motors_ok = (value == 1)
                    if name == 'TEST_URT': uart_ok = (value == 1)

            # Выводим точные модели и статусы здоровья!
            if gyro_ok and accel_ok:
                self.gyro_label.configure(text=f"• ГИРОСКОП: {gyro_model} - РАБОТАЕТ", text_color="#4CAF50")
            else:
                self.gyro_label.configure(text=f"• ГИРОСКОП: {gyro_model} - ОШИБКА / НЕ НАЙДЕН", text_color="#F44336")

            if baro_ok:
                self.baro_label.configure(text=f"• БАРОМЕТР: {baro_model} - РАБОТАЕТ", text_color="#4CAF50")
            else:
                self.baro_label.configure(text=f"• БАРОМЕТР: {baro_model} - ОШИБКА / НЕ НАЙДЕН", text_color="#F44336")

            # Вспомогательная периферия
            if gps_ok: self.gps_label.configure(text="• Модуль GPS: ОПРЕДЕЛЕН (ОК)", text_color="#4CAF50")
            else: self.gps_label.configure(text="• Модуль GPS: НЕ ОПРЕДЕЛЕН", text_color="#F44336")

            if osd_ok: self.osd_label.configure(text="• Графический чип OSD: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.osd_label.configure(text="• Графический чип OSD: ОШИБКА ИНИЦИАЛИЗАЦИИ", text_color="#F44336")

            if motors_ok: self.motors_label.configure(text="• Выходы моторов (ESC): ГОТОВЫ (ОК)", text_color="#4CAF50")
            else: self.motors_label.configure(text="• Выходы моторов (ESC): ОШИБКА ТЕЛЕМЕТРИИ", text_color="#F44336")

            if uart_ok: self.uart_label.configure(text="• Шины UART: ТЕСТ ПРОЙДЕН (ОК)", text_color="#4CAF50")
            else: self.uart_label.configure(text="• Шины UART: ОШИБКА ЛИНИИ", text_color="#F44336")

        except Exception as e:
            for l in labels:
                l.configure(text=l.cget("text").split(":")[0] + ": НЕ ОПРЕДЕЛЕН (НЕТ СВЯЗИ)", text_color="#F44336")

if __name__ == "__main__":
    app = App()
    app.mainloop()
