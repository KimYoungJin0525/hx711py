import RPi.GPIO as GPIO
import time
import threading

class HX711:
    def __init__(self, dout, pd_sck, gain=128):
        # GPIO 핀 설정
        self.PD_SCK = pd_sck
        self.DOUT = dout
        self.readLock = threading.Lock()

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.PD_SCK, GPIO.OUT)
        GPIO.setup(self.DOUT, GPIO.IN)

        self.GAIN = None
        self.setGain(gain)
        time.sleep(1)  # 설정 후 안정화 시간 대기

    def setGain(self, gain):
        # 증폭률 설정 (128, 64, 32)
        if gain == 128:
            self.GAIN = 1
        elif gain == 64:
            self.GAIN = 3
        elif gain == 32:
            self.GAIN = 2
        else:
            return False
        
        self.reset()
        GPIO.output(self.PD_SCK, False)
        self.readRawBytes()  # 첫 샘플은 무효화
        return True

    def reset(self):
        # HX711을 재설정
        self.powerDown()
        self.powerUp()

    def powerDown(self):
        # 전력 절약 모드로 HX711 전원을 끔
        self.readLock.acquire()
        GPIO.output(self.PD_SCK, False)
        GPIO.output(self.PD_SCK, True)
        time.sleep(0.0001)
        self.readLock.release()

    def powerUp(self):
        # HX711 전원을 켬
        self.readLock.acquire()
        GPIO.output(self.PD_SCK, False)
        time.sleep(0.0001)
        self.readLock.release()

    def isReady(self):
        # 데이터 준비 상태 확인
        return GPIO.input(self.DOUT) == GPIO.LOW

    def readNextBit(self):
        # 다음 비트 읽기
        GPIO.output(self.PD_SCK, True)
        GPIO.output(self.PD_SCK, False)
        return int(GPIO.input(self.DOUT))

    def readRawBytes(self):
        # 3바이트 (24비트) 데이터를 읽음
        self.readLock.acquire()
        while not self.isReady():
            pass  # 데이터 준비될 때까지 대기
        
        firstByte = self.readNextByte()
        secondByte = self.readNextByte()
        thirdByte = self.readNextByte()
        
        for i in range(self.GAIN):
            self.readNextBit()  # 증폭률에 따른 추가 비트 처리
        
        self.readLock.release()
        return [firstByte, secondByte, thirdByte]

    def readNextByte(self):
        # 1바이트(8비트) 읽기
        byteValue = 0
        for _ in range(8):
            byteValue <<= 1
            byteValue |= self.readNextBit()
        return byteValue

    def getWeight(self):
        # 원시 데이터를 정수로 변환하여 압력 또는 무게 출력
        rawBytes = self.readRawBytes()
        rawValue = (rawBytes[0] << 16) | (rawBytes[1] << 8) | rawBytes[2]

        # 부호 비트가 설정되면 24비트 값을 음수로 변환
        if rawValue & 0x800000:
            rawValue -= 0x1000000

        return rawValue

# GPIO 핀 번호 설정 (예: dout = 5, pd_sck = 6)
hx711 = HX711(dout=5, pd_sck=6)

try:
    while True:
        weight = hx711.getWeight()  # 압력 또는 무게 데이터 읽기
        print(f"압력 값: {weight}")
        time.sleep(0.1)  # 데이터 출력 간격 조절 (0.1초 대기)
except KeyboardInterrupt:
    GPIO.cleanup()  # Ctrl+C로 종료 시 GPIO 핀 정리
