import RPi.GPIO as GPIO
import time
import threading

class HX711:

    def __init__(self, dout, pd_sck, gain=128):
        """HX711 초기화. Gain 값 설정, GPIO 핀 모드 설정, 참조 및 오프셋 값 초기화"""
        self.PD_SCK = pd_sck  # SCK 핀
        self.DOUT = dout      # DOUT 핀
        self.readLock = threading.Lock()

        # GPIO 초기화
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.PD_SCK, GPIO.OUT)
        GPIO.setup(self.DOUT, GPIO.IN)

        # 보정값 및 참조값 초기화
        self.REFERENCE_UNIT_A = 1  # 기준 단위
        self.OFFSET_A = 1          # 오프셋 값
        self.GAIN = None
        self.setGain(gain)         # 초기 이득(gain) 설정
        time.sleep(1)
        self.lastVal = int(0)

    def powerDown(self):
        """HX711 모듈을 절전 모드로 전환"""
        self.readLock.acquire()
        GPIO.output(self.PD_SCK, False)
        GPIO.output(self.PD_SCK, True)
        time.sleep(0.0001)
        self.readLock.release()

    def powerUp(self):
        """HX711 모듈을 다시 활성화"""
        self.readLock.acquire()
        GPIO.output(self.PD_SCK, False)
        time.sleep(0.0001)
        self.readLock.release()

        # Gain이 128이 아닌 경우 다시 읽어들임
        if self.getGain() != 128:
            self.readRawBytes()

    def reset(self):
        """모듈 재설정"""
        self.powerDown()
        self.powerUp()

    def isReady(self):
        """DOUT 핀 상태를 확인하여 데이터가 준비되었는지 반환"""
        return GPIO.input(self.DOUT) == GPIO.LOW

    def setGain(self, gain):
        """Gain 값 설정 (128, 64, 32 지원)"""
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
        self.readRawBytes()
        return True

    def getGain(self):
        """현재 설정된 Gain 값을 반환"""
        if self.GAIN == 1:
            return 128
        elif self.GAIN == 3:
            return 64
        elif self.GAIN == 2:
            return 32
        raise ValueError("HX711::getGain() gain is invalid")

    def readNextBit(self):
        """1비트씩 읽어들임"""
        GPIO.output(self.PD_SCK, True)
        GPIO.output(self.PD_SCK, False)
        bitValue = GPIO.input(self.DOUT)
        return int(bitValue)

    def readNextByte(self):
        """8비트(1바이트)씩 읽어들임"""
        byteValue = 0
        for x in range(8):
            byteValue <<= 1
            byteValue |= self.readNextBit()
        return byteValue

    def readRawBytes(self):
        """데이터 준비 상태에서 3바이트의 원시 데이터를 읽어옴"""
        if self.GAIN is None:
            raise ValueError("HX711::readRawBytes() called without setting gain first!")
        self.readLock.acquire()

        while self.isReady() is not True:
            pass

        # 3바이트의 원시 데이터 읽기
        firstByte = self.readNextByte()
        secondByte = self.readNextByte()
        thirdByte = self.readNextByte()

        # Gain에 맞춰 추가 비트 읽기
        for i in range(self.GAIN):
            self.readNextBit()

        self.readLock.release()
        return [firstByte, secondByte, thirdByte]

    def convertFromTwosComplement24bit(self, inputValue):
        """2의 보수법을 사용하여 24비트 데이터를 부호있는 정수로 변환"""
        return -(inputValue & 0x800000) + (inputValue & 0x7fffff)

    def rawBytesToLong(self, rawBytes=None):
        """읽은 바이트 배열을 정수값으로 변환"""
        if rawBytes is None:
            return None

        twosComplementValue = ((rawBytes[0] << 16) |
                               (rawBytes[1] << 8)  |
                               rawBytes[2])

        signed_int_value = self.convertFromTwosComplement24bit(twosComplementValue)
        self.lastVal = signed_int_value
        return int(signed_int_value)

    def getLong(self):
        """원시 바이트 데이터를 정수로 반환"""
        rawBytes = self.readRawBytes()
        if rawBytes is None:
            return None
        return self.rawBytesToLong(rawBytes)

    def setOffset(self, offset):
        """오프셋 값 설정"""
        self.OFFSET_A = offset

    def getOffset(self):
        """오프셋 값 반환"""
        return self.OFFSET_A

    def setReferenceUnit(self, referenceUnit):
        """기준 단위 설정"""
        self.REFERENCE_UNIT_A = referenceUnit

    def getReferenceUnit(self):
        """기준 단위 반환"""
        return self.REFERENCE_UNIT_A

    def rawBytesToWeight(self, rawBytes=None):
        """원시 바이트 데이터를 무게(kg)로 변환"""
        if rawBytes is None:
            return None

        # 오프셋을 적용한 후 참조 단위로 나눠 무게 계산
        longWithOffset = self.rawBytesToLong(rawBytes) - self.getOffset()
        referenceUnit = self.getReferenceUnit()

        # 무게를 kg 단위로 변환
        weight = longWithOffset / referenceUnit
        return weight

    def getWeight(self):
        """현재 센서에서 측정한 무게를 반환"""
        rawBytes = self.readRawBytes()
        if rawBytes is None:
            return None
        return self.rawBytesToWeight(rawBytes)

    def tare(self):
        """현재 상태에서의 오프셋 값을 설정하여 무게 보정"""
        # 초기 상태에서 센서 값을 읽어 평균 오프셋 계산
        rawBytes = self.readRawBytes()
        self.setOffset(self.rawBytesToLong(rawBytes))

    def calibrate(self, knownWeight):
        """보정: 알고 있는 무게로 참조 단위를 설정"""
        rawBytes = self.readRawBytes()

        # 현재 읽은 값을 이용하여 기준 단위 설정
        measuredValue = self.rawBytesToLong(rawBytes) - self.getOffset()
        self.setReferenceUnit(measuredValue / knownWeight)


# 예시 코드: 20kg 로드셀에서 무게 측정
dout_pin = 5  # DOUT 핀 번호
pd_sck_pin = 6  # SCK 핀 번호
hx = HX711(dout_pin, pd_sck_pin)

# 초기 보정값 설정 (tare)
hx.tare()

# 알고 있는 무게로 기준 단위 설정 (예: 10kg 물체)
known_weight = 10.0
hx.calibrate(known_weight)

while True:
    weight = hx.getWeight()  # 현재 측정된 무게
    print(f"현재 무게: {weight:.2f} kg")
    time.sleep(1)  # 1초마다 측정값 출력
