import time
import sys
import RPi.GPIO as GPIO
from hx711 import HX711

def cleanAndExit():
    print("Cleaning...")
    GPIO.cleanup()  # GPIO 핀 해제
    print("Bye!")
    sys.exit()

# 첫 번째 HX711 - 엑셀(Accelerator)
hx1 = HX711(5, 6)  # 첫 번째 HX711의 데이터 핀과 클럭 핀

# 두 번째 HX711 - 브레이크(Brake) 첫번째 완성후 넘어갈것
# hx2 = HX711(13, 19)  # 두 번째 HX711의 데이터 핀과 클럭 핀

# MSB 순서로 설정
hx1.set_reading_format("MSB", "MSB")
# hx2.set_reading_format("MSB", "MSB") 첫번째 완성후 넘어갈것

# 참조 단위 설정 (로드셀 보정값)
referenceUnit = 114
hx1.set_reference_unit(referenceUnit)
# hx2.set_reference_unit(referenceUnit) 첫번째 완성후 넘어갈것

# 초기화 및 영점 설정
hx1.reset()
# hx2.reset() 첫번째 완성후 넘어갈것

hx1.tare()
# hx2.tare() 첫번째 완성후 넘어갈것

print("Tare done! Add weight now...")

while True:
    try:
        # 첫 번째 로드셀 (엑셀)
        val_accelerator = hx1.get_weight(5)
        print(f"엑셀 (Accelerator) 무게: {val_accelerator} g")

        # 두 번째 로드셀 (브레이크)
        #val_brake = hx2.get_weight(5)
        # print(f"브레이크 (Brake) 무게: {val_brake} g")

        hx1.power_down()
        # hx2.power_down()
        hx1.power_up()
        # hx2.power_up()
        time.sleep(0.1)

    except (KeyboardInterrupt, SystemExit):
        cleanAndExit()
