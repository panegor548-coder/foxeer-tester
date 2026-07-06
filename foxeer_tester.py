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

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Foxeer F405 Advanced Tester")
        self.geometry("500x560")  # Немного увеличили окно под новые датчики
        self.resizable(False, False)

        # Главный заголовок
        self.title_label = ctk.CTkLabel(
            self, text="Расширенный тестер Foxeer v2.3", 
            font=ctk.CTkFont(family="Arial", size=22, weight="bold")
        )
        self.title_label.pack(pady=(25, 15))

        # Выбор порта
        self.port_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.port_frame.pack(pady=5, fill="x", padx=40)

        self.port_label = ctk.CTkLabel(self.port_frame, text="Выбор порта:", font=ctk.CTkFont(size=14))
        self.port_label.pack(side="left", padx=(0, 10))

        self.selected_port = tk.StringVar()
        self.port_menu = ctk.CTkOptionMenu(self.port_frame, width=200, variable=self.selected_port)
        self.port_menu.pack(side="left", expand=True, fill="x", padx=(0, 10))

        self.refresh_button = ctk.CTkButton(self.port_frame, text="🔄", width=45, font=ctk.CTkFont(size=16), command=self.update_ports_list)
        self.refresh_button.pack(side="right")

        self.update_ports_list()

        # Кнопка ПРОВЕРИТЬ
        self.check_button = ctk.CTkButton(
            self, text="ЗАПУСТИТЬ ПОЛНЫЙ ТЕСТ ПЛАТЫ", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45, corner_radius=8,
            command=self.check_sensors
        )
        self.check_button.pack(pady=15, padx=40, fill="x")

        # Карточка результатов
        self.result_frame = ctk.CTkFrame(self, corner_radius=10)
        self.result_frame.pack(pady=10, fill="both", padx=40, expand=True)

        # Базовые датчики платы
        self.gyro_label = ctk.CTkLabel(self.result_frame, text="• ГИРОСКОП & АКСЕЛЬ: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.gyro_label.pack(anchor="w", padx=20, pady=(12, 4))

        self.baro_label = ctk.CTkLabel(self.result_frame, text="• БАРОМЕТР (DPS310): Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.baro_label.pack(anchor="w", padx=20, pady=4)

        # Новое периферийное оборудование (запрашивается у мини-прошивки)
        self.gps_label = ctk.CTkLabel(self.result_frame, text="• Модуль GPS: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.gps_label.pack(anchor="w", padx=20, pady=4)

        self.osd_label = ctk.CTkLabel(self.result_frame, text="• Графический чип OSD: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.osd_label.pack(anchor="w", padx=20, pady=4)

        self.motors_label = ctk.CTkLabel(self.result_frame, text="• Выходы моторов (ESC): Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.motors_label.pack(anchor="w", padx=20, pady=4)

        self.uart_label = ctk.CTkLabel(self.result_frame, text="• Аппаратные шины UART: Ожидание", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        self.uart_label.pack(anchor="w", padx=20, pady=(4, 12))

    def update_ports_list(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        if ports:
            self.port_menu.configure(values=ports)
            if self.selected_port.get() not in ports: self.selected_port.set(ports[0])
        else:
            self.port_menu.configure(values=["Порты не найдены"])
            self.selected_port.set("Порты не найдены")

    def check_sensors(self):
        port = self.selected_port.get()
        if not port or port == "Порты не найдены":
            messagebox.showwarning("Внимание", "Подключите плату!")
            return
        
        # Сброс статусов в "Опрос..."
        labels = [self.gyro_label, self.baro_label, self.gps_label, self.osd_label, self.motors_label, self.uart_label]
        for l in labels:
            l.configure(text=l.cget("text").split(":")[0] + ": Опрос...", text_color="#FF9800")
        self.update()

        try:
            master = mavutil.mavlink_connection(port, baud=115200)
            msg = master.wait_heartbeat(timeout=2.5)
            if not msg: raise Exception("Нет связи")

            master.mav.request_data_stream_send(master.target_system, master.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)

            # Переменные под статусы
            gyro_ok = accel_ok = baro_ok = False
            gps_ok = osd_ok = motors_ok = uart_ok = False
            
            start_time = time.time()
            while time.time() - start_time < 3.0:
                msg = master.recv_match(blocking=True, timeout=0.1)
                if not msg: continue

                # 1. Читаем базовое состояние здоровья из стандартного пакета
                if msg.get_type() == 'SYS_STATUS':
                    health = msg.onboard_control_sensors_health
                    gyro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO)
                    accel_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL)
                    baro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE)
                
                # 2. Ищем кастомные данные от нашего Lua-скрипта из мини-прошивки по именам
                elif msg.get_type() == 'NAMED_VALUE_INT':
                    name = msg.name.strip()
                    value = msg.value
                    if name == 'TEST_GPS': gps_ok = (value == 1)
                    if name == 'TEST_OSD': osd_ok = (value == 1)
                    if name == 'TEST_MOT': motors_ok = (value == 1)
                    if name == 'TEST_URT': uart_ok = (value == 1)

            # Вывод результатов IMU
            if gyro_ok and accel_ok: self.gyro_label.configure(text="• ГИРОСКОП & АКСЕЛЬ: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.gyro_label.configure(text="• ГИРОСКОП & АКСЕЛЬ: НЕ ОПРЕДЕЛЕН", text_color="#F44336")

            # Вывод Барометра
            if baro_ok: self.baro_label.configure(text="• БАРОМЕТР (DPS310): РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.baro_label.configure(text="• БАРОМЕТР (DPS310): НЕ ОПРЕДЕЛЕН", text_color="#F44336")

            # Вывод GPS
            if gps_ok: self.gps_label.configure(text="• Модуль GPS: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.gps_label.configure(text="• Модуль GPS: НЕ ОПРЕДЕЛЕН / ОШИБКА", text_color="#F44336")

            # Вывод OSD
            if osd_ok: self.osd_label.configure(text="• Графический чип OSD: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.osd_label.configure(text="• Графический чип OSD: ОШИБКА ИНИЦИАЛИЗАЦИИ", text_color="#F44336")

            # Вывод моторов
            if motors_ok: self.motors_label.configure(text="• Выходы моторов (ESC): РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.motors_label.configure(text="• Выходы моторов (ESC): ОШИБКА ШИМ/DSHOT", text_color="#F44336")

            # Вывод UART
            if uart_ok: self.uart_label.configure(text="• Аппаратные шины UART: ТЕСТ ПРОЙДЕН (ОК)", text_color="#4CAF50")
            else: self.uart_label.configure(text="• Аппаратные шины UART: ОШИБКА ПРИЕМА-ПЕРЕДАЧИ", text_color="#F44336")

        except Exception as e:
            for l in labels:
                l.configure(text=l.cget("text").split(":")[0] + ": НЕ ОПРЕДЕЛЕН (НЕТ СВЯЗИ)", text_color="#F44336")

if __name__ == "__main__":
    app = App()
    app.mainloop()
