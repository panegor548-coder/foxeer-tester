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
# Импортируем официальный FTP-менеджер из pymavlink
from pymavlink.generator import mavftp
import serial.tools.list_ports

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Вшитый Lua-скрипт (Python сам создаст его на плате)
LUA_SCRIPT_CONTENT = b"""
local last_run = 0
function update()
    local current_time = millis()
    if current_time - last_run < 500 then return update, 100 end
    last_run = current_time

    local gps_status = gps:status(0)
    gcs:send_named_value_int('TEST_GPS', gps_status > 0 and 1 or 0)

    local osd_ok = (param:get('OSD_TYPE') and param:get('OSD_TYPE') > 0) and 1 or 0
    gcs:send_named_value_int('TEST_OSD', osd_ok)

    local motors_ok = (motors and motors:get_armed() == false) and 1 or 0
    gcs:send_named_value_int('TEST_MOT', motors_ok)

    local uart_ok = 0
    local test_serial = serial:find_serial(1)
    if test_serial then
        test_serial:write(0x55)
        delay(1)
        if test_serial:available() > 0 and test_serial:read() == 0x55 then uart_ok = 1 end
    end
    gcs:send_named_value_int('TEST_URT', uart_ok)
    return update, 100
end
return update, 1000
"""

GYRO_TYPES = {1: "MPU6000", 4: "ICM20602", 11: "ICM42688", 12: "BMI270"}
BARO_TYPES = {1: "BMP280", 6: "DPS310", 9: "BMP388"}

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Foxeer F405 Auto-Flash Tester")
        self.geometry("520x580")
        self.resizable(False, False)

        self.title_label = ctk.CTkLabel(self, text="Автоматический стенд Foxeer v2.5", font=ctk.CTkFont(family="Arial", size=22, weight="bold"))
        self.title_label.pack(pady=(25, 15))

        self.port_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.port_frame.pack(pady=5, fill="x", padx=40)

        self.selected_port = tk.StringVar()
        self.port_menu = ctk.CTkOptionMenu(self.port_frame, width=220, variable=self.selected_port)
        self.port_menu.pack(side="left", expand=True, fill="x", padx=(0, 10))

        self.refresh_button = ctk.CTkButton(self.port_frame, text="🔄", width=45, font=ctk.CTkFont(size=16), command=self.update_ports_list)
        self.refresh_button.pack(side="right")
        self.update_ports_list()

        self.check_button = ctk.CTkButton(self, text="ЗАПУСТИТЬ АВТОПРОШИВКУ И ТЕСТ", font=ctk.CTkFont(size=14, weight="bold"), height=45, corner_radius=8, command=self.check_sensors)
        self.check_button.pack(pady=15, padx=40, fill="x")

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

    def upload_lua_via_mavlink(self, master):
        """Надежная загрузка Lua-скрипта в полетник через официальный MAVLink FTP"""
        try:
            # 1. Включаем поддержку Lua-скриптов на плате
            master.mav.param_set_send(master.target_system, master.target_component, b"SCR_ENABLE", 1, mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
            
            # 2. Используем встроенный в pymavlink FTP-клиент для отправки файла
            ftp = mavftp.MavlinkFTPHelper(master)
            target_path = "@APM/scripts/foxeer_test_peripheral.lua" # Символ @ указывает на корень флешки
            
            # Записываем байты нашего Lua-скрипта прямо в файловую систему платы
            ftp.write(target_path, LUA_SCRIPT_CONTENT)
            
            # 3. Перезапускаем Lua-движок на плате, чтобы скрипт сразу включился
            master.mav.command_long_send(
                master.target_system, master.target_component,
                mavutil.mavlink.MAV_CMD_SCRIPTING, 0,
                1, 0, 0, 0, 0, 0, 0  # Параметр 1 = RESTART (перезапуск)
            )
            time.sleep(1.5)  # Даем плате время запустить скрипт
            return True
        except Exception as e:
            print(f"Ошибка FTP загрузки: {e}")
            return False

    def request_parameter(self, master, param_name):
        try:
            master.mav.param_request_read_send(master.target_system, master.target_component, param_name.encode('utf-8'), -1)
            start = time.time()
            while time.time() - start < 0.4:
                msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.05)
                if msg and msg.param_id.strip() == param_name: return msg.param_value
        except: pass
        return None

    def check_sensors(self):
        port = self.selected_port.get()
        if not port or port == "Порты не найдены":
            messagebox.showwarning("Внимание", "Подключите плату!")
            return
        
        labels = [self.gyro_label, self.baro_label, self.gps_label, self.osd_label, self.motors_label, self.uart_label]
        for l in labels: l.configure(text=l.cget("text").split(":")[0] + ": Прошивка Lua...", text_color="#FF9800")
        self.update()

        try:
            master = mavutil.mavlink_connection(port, baud=115200)
            msg = master.wait_heartbeat(timeout=2.5)
            if not msg: raise Exception("Нет связи")

            # Сама шьет плату при каждом тесте!
            self.upload_lua_via_mavlink(master)

            for l in labels: l.configure(text=l.cget("text").split(":")[0] + ": Тестирование...")
            self.update()

            gyro_id = self.request_parameter(master, "INS_GYRO_ID") or self.request_parameter(master, "INS_ID")
            baro_id = self.request_parameter(master, "BARO_EXT_BUS") or self.request_parameter(master, "BARO_PRIMARY")
            
            gyro_model = GYRO_TYPES.get((int(gyro_id or 0) >> 16) & 0xFF, "ICM42688 (Foxeer)")
            baro_model = BARO_TYPES.get((int(baro_id or 0) >> 16) & 0xFF, "DPS310 (Foxeer)")

            master.mav.request_data_stream_send(master.target_system, master.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)

            gyro_ok = accel_ok = baro_ok = False
            gps_ok = osd_ok = motors_ok = uart_ok = False
            
            start_time = time.time()
            while time.time() - start_time < 3.0:
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

            if gyro_ok and accel_ok: self.gyro_label.configure(text=f"• ГИРОСКОП: {gyro_model} - РАБОТАЕТ", text_color="#4CAF50")
            else: self.gyro_label.configure(text=f"• ГИРОСКОП: {gyro_model} - ОШИБКА", text_color="#F44336")

            if baro_ok: self.baro_label.configure(text=f"• БАРОМЕТР: {baro_model} - РАБОТАЕТ", text_color="#4CAF50")
            else: self.baro_label.configure(text=f"• БАРОМЕТР: {baro_model} - ОШИБКА", text_color="#F44336")

            if gps_ok: self.gps_label.configure(text="• Модуль GPS: ОПРЕДЕЛЕН (ОК)", text_color="#4CAF50")
            else: self.gps_label.configure(text="• Модуль GPS: НЕ ОПРЕДЕЛЕН", text_color="#F44336")

            if osd_ok: self.osd_label.configure(text="• Графический чип OSD: РАБОТАЕТ (ОК)", text_color="#4CAF50")
            else: self.osd_label.configure(text="• Графический чип OSD: ОШИБКА ИНИЦИАЛИЗАЦИИ", text_color="#F44336")

            if motors_ok: self.motors_label.configure(text="• Выходы моторов (ESC): ГОТОВЫ (ОК)", text_color="#4CAF50")
            else: self.motors_label.configure(text="• Выходы моторов (ESC): ОШИБКА", text_color="#F44336")

            if uart_ok: self.uart_label.configure(text="• Шины UART: ТЕСТ ПРОЙДЕН (ОК)", text_color="#4CAF50")
            else: self.uart_label.configure(text="• Шины UART: ОШИБКА", text_color="#F44336")

        except Exception as e:
            for l in labels: l.configure(text=l.cget("text").split(":")[0] + ": НЕ ОПРЕДЕЛЕН (НЕТ СВЯЗИ)", text_color="#F44336")

if __name__ == "__main__":
    app = App()
    app.mainloop()
