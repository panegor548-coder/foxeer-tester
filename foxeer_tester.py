import time
import sys
import tkinter as tk
from tkinter import messagebox
import subprocess

# Автоматически доустановим красивую библиотеку, если её нет на компьютере
try:
    import customtkinter as ctk
except ImportError:
    import os
    print("Установка красивой темы (customtkinter)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from pymavlink import mavutil
import serial.tools.list_ports  # Модуль для автоматического поиска портов

# Настройки оформления
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Foxeer F405 Sensor Tester")
        self.geometry("460x440")
        self.resizable(False, False)

        # Главный заголовок
        self.title_label = ctk.CTkLabel(
            self, text="Тестер датчиков Foxeer v2.2", 
            font=ctk.CTkFont(family="Arial", size=22, weight="bold")
        )
        self.title_label.pack(pady=(25, 15))

        # Фрейм для выбора порта
        self.port_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.port_frame.pack(pady=10, fill="x", padx=40)

        self.port_label = ctk.CTkLabel(self.port_frame, text="Выбор порта:", font=ctk.CTkFont(size=14))
        self.port_label.pack(side="left", padx=(0, 10))

        # Переменная для хранения выбранного порта
        self.selected_port = tk.StringVar()
        
        # Выпадающий список (пока пустой, обновим через метод)
        self.port_menu = ctk.CTkOptionMenu(self.port_frame, width=180, variable=self.selected_port)
        self.port_menu.pack(side="left", expand=True, fill="x", padx=(0, 10))

        # Кнопка «Обновить список портов» со значком стрелочек
        self.refresh_button = ctk.CTkButton(
            self, text="🔄", width=40, 
            font=ctk.CTkFont(size=16),
            command=self.update_ports_list
        )
        self.refresh_button.pack(pady=(0, 10))

        # Первичное сканирование портов при запуске
        self.update_ports_list()

        # Кнопка запуска
        self.check_button = ctk.CTkButton(
            self, text="ПРОВЕРИТЬ ДАТЧИКИ", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45, corner_radius=8,
            command=self.check_sensors
        )
        self.check_button.pack(pady=20, padx=40, fill="x")

        # Фрейм для результатов
        self.result_frame = ctk.CTkFrame(self, corner_radius=10)
        self.result_frame.pack(pady=10, fill="both", padx=40, expand=True)

        # Строки статусов датчиков
        self.gyro_label = ctk.CTkLabel(self.result_frame, text="• ГИРОСКОП (ICM42688): Ожидание", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.gyro_label.pack(anchor="w", padx=20, pady=(15, 5))

        self.accel_label = ctk.CTkLabel(self.result_frame, text="• АКСЕЛЕРОМЕТР: Ожидание", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.accel_label.pack(anchor="w", padx=20, pady=5)

        self.baro_label = ctk.CTkLabel(self.result_frame, text="• БАРОМЕТР (DPS310): Ожидание", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.baro_label.pack(anchor="w", padx=20, pady=(5, 15))

    def update_ports_list(self):
        """Автоматически находит все подключенные устройства и обновляет список"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        if ports:
            # Если порты найдены, обновляем выпадающий список
            self.port_menu.configure(values=ports)
            # Если текущий выбранный порт пропал или еще не выбран, ставим первый из списка
            if self.selected_port.get() not in ports:
                self.selected_port.set(ports[0])
        else:
            # Если ничего не подключено
            self.port_menu.configure(values=["Порты не найдены"])
            self.selected_port.set("Порты не найдены")

    def check_sensors(self):
        port = self.selected_port.get()
        if not port or port == "Порты не найдены":
            messagebox.showwarning("Внимание", "Подключите полетный контроллер и обновите порты!")
            return
        
        self.gyro_label.configure(text="• ГИРОСКОП: Опрос...", text_color="#FF9800")
        self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: Опрос...", text_color="#FF9800")
        self.baro_label.configure(text="• БАРОМЕТР: Опрос...", text_color="#FF9800")
        self.update()

        try:
            master = mavutil.mavlink_connection(port, baud=115200)
            
            msg = master.wait_heartbeat(timeout=2.5)
            if not msg:
                raise Exception("Таймаут связи")

            master.mav.request_data_stream_send(
                master.target_system, master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
            )

            gyro_ok = accel_ok = baro_ok = False
            start_time = time.time()
            
            while time.time() - start_time < 2.5:
                msg = master.recv_match(blocking=True, timeout=0.1)
                if msg and msg.get_type() == 'SYS_STATUS':
                    health = msg.onboard_control_sensors_health
                    gyro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO)
                    accel_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL)
                    baro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE)
                    break

            if gyro_ok: self.gyro_label.configure(text="• ГИРОСКОП: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.gyro_label.configure(text="• ГИРОСКОП: НЕ ОПРЕДЕЛЕН / ОШИБКА", text_color="#F44336")

            if accel_ok: self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: НЕ ОПРЕДЕЛЕН / ОШИБКА", text_color="#F44336")

            if baro_ok: self.baro_label.configure(text="• БАРОМЕТР: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.baro_label.configure(text="• БАРОМЕТР: НЕ ОПРЕДЕЛЕН / ОШИБКА", text_color="#F44336")

        except Exception as e:
            # Если порт занят Betaflight-ом или отключен кабель — выводим "НЕ ОПРЕДЕЛЕН" без системных ошибок
            self.gyro_label.configure(text="• ГИРОСКОП: НЕ ОПРЕДЕЛЕН (НЕТ СВЯЗИ)", text_color="#F44336")
            self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: НЕ ОПРЕДЕЛЕН (НЕТ СВЯЗИ)", text_color="#F44336")
            self.baro_label.configure(text="• БАРОМЕТР: НЕ ОПРЕДЕЛЕН (НЕТ СВЯЗИ)", text_color="#F44336")

if __name__ == "__main__":
    app = App()
    app.mainloop()
