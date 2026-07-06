import time
from pymavlink import mavutil

# Твой порт на Mac
COM_PORT = '/dev/cu.usbmodem101' 
BAUD_RATE = 115200

print("======= ТЕСТЕР ДАТЧИКОВ FOXEER =======")
print(f"1. Подключение к {COM_PORT}...")
master = mavutil.mavlink_connection(COM_PORT, baud=BAUD_RATE)

# Ждем первый пакет связи
master.wait_heartbeat()
print("   [ОК] Связь с платой установлена.")

# --- ЗАСТАВЛЯЕМ ПЛАТУ ОТВЕЧАТЬ ---
# Просим плату слать системный статус и данные датчиков с частотой 10 Гц
master.mav.request_data_stream_send(
    master.target_system, 
    master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL, # Просим все данные, включая SYS_STATUS
    10,  # 10 раз в секунду
    1    # Включить поток
)
print("2. Опрос датчиков полетного контроллера...")

# Переменные для результатов
gyro_status = "НЕОПРЕДЕЛЕН (НЕТ ДАННЫХ)"
accel_status = "НЕОПРЕДЕЛЕН (НЕТ ДАННЫХ)"
baro_status = "НЕОПРЕДЕЛЕН (НЕТ ДАННЫХ)"

start_time = time.time()
timeout = 5.0  # Ждем ответа не больше 5 секунд

while True:
    if time.time() - start_time > timeout:
        print("   [!] Время ожидания ответа истекло.")
        break

    # Читаем сообщения
    msg = master.recv_match(blocking=True, timeout=0.1)
    if not msg:
        continue

    # Как только поймали SYS_STATUS, вытаскиваем из него биты "здоровья"
    if msg.get_type() == 'SYS_STATUS':
        health = msg.onboard_control_sensors_health
        
        gyro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_GYRO)
        accel_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_3D_ACCEL)
        baro_ok = bool(health & mavutil.mavlink.MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE)
        
        gyro_status = "РАБОТАЕТ (ОК)" if gyro_ok else "ОШИБКА (НЕ ОТВЕЧАЕТ)"
        accel_status = "РАБОТАЕТ (ОК)" if accel_ok else "ОШИБКА (НЕ ОТВЕЧАЕТ)"
        baro_status = "РАБОТАЕТ (ОК)" if baro_ok else "ОШИБКА (НЕ ОТВЕЧАЕТ)"
        
        # Получили статус — мгновенно выходим из цикла, чтобы не спамить
        break

print("\n======= РЕЗУЛЬТАТЫ ПРОВЕРКИ =======")
print(f"ГИРОСКОП (ICM42688):  {gyro_status}")
print(f"АКСЕЛЕРОМЕТР:         {accel_status}")
print(f"БАРОМЕТР (DPS310):    {baro_status}")
print("====================================")
print("Проверка завершена. Программа закрывается.")
