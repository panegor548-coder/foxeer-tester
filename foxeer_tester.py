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

# Настройки оформления
ctk.set_appearance_mode("System")  # Адаптируется под темную/светлую тему Windows/Mac
ctk.set_default_color_theme("blue") # Основной цвет — стильный синий

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Foxeer F405 Sensor Tester")
        self.geometry("460x420")
        self.resizable(False, False)

        # Главный заголовок
        self.title_label = ctk.CTkLabel(
            self, text="Тестер датчиков Foxeer v2.0", 
            font=ctk.CTkFont(family="Arial", size=22, weight="bold")
        )
        self.title_label.pack(pady=(25, 20))

        # Фрейм для ввода порта
        self.port_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.port_frame.pack(pady=10, fill="x", padx=40)

        self.port_label = ctk.CTkLabel(self.port_frame, text="Порт платы:", font=ctk.CTkFont(size=14))
        self.port_label.pack(side="left", padx=(0, 10))

        # Определяем порт по умолчанию в зависимости от системы
        default_port = "/dev/cu.usbmodem101" if sys.platform == "darwin" else "COM3"
        self.port_entry = ctk.CTkEntry(self.port_frame, width=220, font=ctk.CTkFont(size=14))
        self.port_entry.insert(0, default_port)
        self.port_entry.pack(side="right", expand=True, fill="x")

        # Кнопка запуска с красивым скруглением
        self.check_button = ctk.CTkButton(
            self, text="ПРОВЕРИТЬ ДАТЧИКИ", 
            font=ctk.CTkFont(size=14, weight="bold"),
            height=45, corner_radius=8,
            command=self.check_sensors
        )
        self.check_button.pack(pady=25, padx=40, fill="x")

        # Фрейм для результатов (в виде карточки)
        self.result_frame = ctk.CTkFrame(self, corner_radius=10)
        self.result_frame.pack(pady=10, fill="both", padx=40, expand=True)

        # Строки статусов датчиков
        self.gyro_label = ctk.CTkLabel(self.result_frame, text="• ГИРОСКОП (ICM42688): Ожидание", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.gyro_label.pack(anchor="w", padx=20, pady=(15, 5))

        self.accel_label = ctk.CTkLabel(self.result_frame, text="• АКСЕЛЕРОМЕТР: Ожидание", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.accel_label.pack(anchor="w", padx=20, pady=5)

        self.baro_label = ctk.CTkLabel(self.result_frame, text="• БАРОМЕТР (DPS310): Ожидание", font=ctk.CTkFont(size=14, weight="bold"), text_color="gray")
        self.baro_label.pack(anchor="w", padx=20, pady=(5, 15))

    def check_sensors(self):
        port = self.port_entry.get().strip()
        if not port:
            messagebox.showerror("Ошибка", "Пожалуйста, укажите порт!")
            return
        
        # Ставим статус "Опрос..." оранжевым цветом
        self.gyro_label.configure(text="• ГИРОСКОП: Опрос...", text_color="#FF9800")
        self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: Опрос...", text_color="#FF9800")
        self.baro_label.configure(text="• БАРОМЕТР: Опрос...", text_color="#FF9800")
        self.update()

        try:
            master = mavutil.mavlink_connection(port, baud=115200)
            msg = master.wait_heartbeat(timeout=3.0)
            if not msg:
                raise Exception("Плата не отвечает (таймаут heartbeat)")

            master.mav.request_data_stream_send(
                master.target_system, master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
            )

            gyro_ok = accel_ok = baro_ok = False
            start_time = time.time()
            
            while time.time() - start_time < 3.0:
                msg = master.recv_match(blocking=True, timeout=0.1)
                if msg and msg.get_type() == 'SYS_STATUS':
                    health = msg.onboard_control_sensors_health
                    gyro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO)
                    accel_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL)
                    baro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE)
                    break

            # Обновляем красивыми цветами (Зеленый / Красный)
            if gyro_ok: self.gyro_label.configure(text="• ГИРОСКОП: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.gyro_label.configure(text="• ГИРОСКОП: ОШИБКА", text_color="#F44336")

            if accel_ok: self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: ОШИБКА", text_color="#F44336")

            if baro_ok: self.baro_label.configure(text="• БАРОМЕТР: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.baro_label.configure(text="• БАРОМЕТР: ОШИБКА", text_color="#F44336")

        except Exception as e:
            messagebox.showerror("Ошибка подключения", f"Не удалось связаться с платой.\n{str(e)}")
            self.gyro_label.configure(text="• ГИРОСКОП: нет данных", text_color="gray")
            self.accel_label.configure(text="• АКСЕЛЕРОМЕТР: нет данных", text_color="gray")
            self.baro_label.configure(text="• БАРОМЕТР: нет данных", text_color="gray")

if __name__ == "__main__":
    app = App()
    app.mainloop()
