import RPi.GPIO as GPIO
import time
import threading

class HX711:
    def __init__(self, dout, pd_sck, gain=128):
        self.PD_SCK = pd_sck  # HX711의 클럭 핀 번호
        self.DOUT = dout      # HX711의 데이터 출력 핀 번호

        # 여러 스레드가 동시에 HX711에서 데이터를 읽으려 할 때를 대비한 잠금 객체
        self.readLock = threading.Lock()
        
        # GPIO 핀 모드 설정 (BCM 모드 사용)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.PD_SCK, GPIO.OUT)  # 클럭 핀을 출력으로 설정
        GPIO.setup(self.DOUT, GPIO.IN)     # 데이터 핀을 입력으로 설정

        # 참조 단위 설정 (무게 계산을 위한 기준 값)
        self.REFERENCE_UNIT_A = 1
        self.REFERENCE_UNIT_B = 1

        # 오프셋 설정 (무게 측정의 기준점)
        self.OFFSET_A = 1
        self.OFFSET_B = 1
        self.lastVal = int(0)  # 마지막으로 읽은 값 저장

        # 바이트와 비트의 순서 설정 ('MSB' 또는 'LSB')
        self.byteFormat = 'MSB'
        self.bitFormat = 'MSB'
        
        # 초기 증폭 설정 (1: 128, 2: 32, 3: 64)
        self.GAIN = None
        self.setGain(gain)

        # 초기화 후 안정화를 위해 잠시 대기
        time.sleep(1)
        time.sleep(1)
        
        # 데이터 준비 콜백 설정
        self.readyCallbackEnabled = False
        self.paramCallback = None
        self.lastRawBytes = None

    def powerDown(self):
        """
        HX711을 절전 모드로 전환합니다.
        """
        # 읽기 잠금을 획득하여 다른 스레드가 접근하지 못하게 함
        self.readLock.acquire()

        # 클럭 신호를 상승시켜 HX711을 절전 모드로 전환
        GPIO.output(self.PD_SCK, False)
        GPIO.output(self.PD_SCK, True)

        # 절전 모드로 전환될 때까지 잠시 대기
        time.sleep(0.0001)

        # 읽기 잠금을 해제
        self.readLock.release()

    def powerUp(self):
        """
        HX711을 절전 모드에서 해제하고 활성화합니다.
        """
        # 읽기 잠금을 획득
        self.readLock.acquire()

        # 클럭 신호를 낮춰 HX711을 활성화
        GPIO.output(self.PD_SCK, False)

        # HX711이 활성화될 때까지 잠시 대기
        time.sleep(0.0001)

        # 읽기 잠금을 해제
        self.readLock.release()

        # 현재 설정된 증폭 값이 128이 아니면, 한 번 샘플을 읽어 설정을 적용
        if self.getGain() != 128:
            self.readRawBytes()

    def reset(self):
        """
        HX711을 재시작(리셋)합니다.
        """
        self.powerDown()
        self.powerUp()

    def isReady(self):
        """
        HX711이 데이터를 읽을 준비가 되었는지 확인합니다.
        DOUT 핀이 LOW일 때 준비 완료 상태로 판단합니다.
        """
        return GPIO.input(self.DOUT) == GPIO.LOW

    def setGain(self, gain):
        """
        HX711의 증폭 설정을 변경합니다.
        gain: 128, 64, 32 중 하나
        """
        if gain == 128:
            self.GAIN = 1
        elif gain == 64:
            self.GAIN = 3
        elif gain == 32:
            self.GAIN = 2
        else:
            return False
        
        self.reset()  # 설정 변경을 위해 리셋 호출

        GPIO.output(self.PD_SCK, False)

        # 초기화 후 첫 데이터를 읽고 무시하여 설정을 적용
        self.readRawBytes()
        
        return True

    def getGain(self):
        """
        현재 설정된 증폭 값을 반환합니다.
        """
        if self.GAIN == 1:
            return 128
        elif self.GAIN == 3:
            return 64
        elif self.GAIN == 2:
            return 32

        raise ValueError("HX711::getGain() gain이 현재 유효하지 않은 값입니다.")

    def setChannel(self, channel='A'):
        """
        HX711의 채널을 설정합니다.
        channel: 'A' 또는 'B'
        """
        if channel == 'A':
            self.setGain(128)
            return True
        elif channel == 'B':
            self.setGain(32)
            return True
        
        raise ValueError(f"HX711::setChannel() 잘못된 채널: \"{channel}\"")

    def getChannel(self):
        """
        현재 설정된 채널을 반환합니다.
        """
        if self.GAIN == 1 or self.GAIN == 3:
            return 'A'
        elif self.GAIN == 2:
            return 'B'
        
        raise ValueError("HX711::getChannel() gain이 현재 유효하지 않은 값입니다.")

    def readNextBit(self):
        """
        HX711에서 다음 비트를 읽어옵니다.
        """
        # 클럭 신호를 상승시켰다가 다시 낮춤
        GPIO.output(self.PD_SCK, True)
        GPIO.output(self.PD_SCK, False)
        bitValue = GPIO.input(self.DOUT)

        # Boolean 값을 정수로 변환하여 반환
        return int(bitValue)

    def readNextByte(self):
        """
        HX711에서 다음 바이트(8비트)를 읽어옵니다.
        """
        byteValue = 0

        # 비트 순서에 따라 바이트 값을 구성
        for x in range(8):
            if self.bitFormat == 'MSB':
                # 상위 비트부터 읽기
                byteValue <<= 1
                byteValue |= self.readNextBit()
            else:
                # 하위 비트부터 읽기
                byteValue >>= 1              
                byteValue |= self.readNextBit() * 0x80

        # 구성된 바이트 값을 반환
        return byteValue 

    def readRawBytes(self, blockUntilReady=True):
        """
        HX711에서 원시 바이트(3바이트)를 읽어옵니다.
        blockUntilReady: 데이터가 준비될 때까지 대기할지 여부
        """
        if self.GAIN is None:
            raise ValueError("HX711::readRawBytes() gain 설정 없이 호출됨!")

        # 읽기 잠금을 시도
        if not self.readLock.acquire(blockUntilReady):
            # 잠금을 획득하지 못하면 읽기를 건너뜀
            return None

        # HX711이 데이터를 준비할 때까지 대기
        while not self.isReady():
            pass

        # 3바이트의 데이터를 읽어옴
        firstByte  = self.readNextByte()
        secondByte = self.readNextByte()
        thirdByte  = self.readNextByte()

        # 증폭 설정에 따라 추가 클럭 신호를 보냄
        for i in range(self.GAIN):
            self.readNextBit()

        # 읽기 잠금 해제
        self.readLock.release()           

        # 바이트 순서에 따라 원시 데이터를 반환
        if self.byteFormat == 'MSB':
            return [firstByte, secondByte, thirdByte]
        else:
            return [thirdByte, secondByte, firstByte]

    def getRawBytes(self, channel='A'):
        """
        특정 채널에서 원시 바이트를 읽어옵니다.
        channel: 'A' 또는 'B'
        """
        # 현재 채널을 저장
        currentChannel = self.getChannel()
        
        # 요청한 채널과 현재 채널이 다르면 채널 변경
        if channel != currentChannel:
            self.setChannel(channel)
        
        rawBytes = self.readRawBytes()
        
        # 채널을 원래대로 복구
        if channel != currentChannel:
            self.setChannel(currentChannel)
        
        return rawBytes

    def getLastRawBytes(self):
        """
        마지막으로 읽은 원시 바이트를 반환하고, 저장된 값을 초기화합니다.
        """
        rawBytes = self.lastRawBytes
        self.lastRawBytes = None
        return rawBytes

    def readyCallback(self, pin):
        """
        HX711의 데이터가 준비되었을 때 호출되는 콜백 함수입니다.
        """
        # DOUT 핀에 대한 콜백인지 확인
        if pin != self.DOUT:
            return
        
        # 원시 데이터를 읽어옴
        self.lastRawBytes = self.readRawBytes(blockUntilReady=False)
        
        # 콜백 함수가 설정되어 있으면 호출
        if self.paramCallback is not None:
            self.paramCallback(self.lastRawBytes)

    def enableReadyCallback(self, paramCallback=None):
        """
        HX711의 데이터 준비 콜백을 활성화합니다.
        paramCallback: 데이터가 준비되었을 때 호출될 함수
        """
        self.paramCallback = paramCallback if paramCallback is not None else self.paramCallback
        GPIO.add_event_detect(self.DOUT, GPIO.FALLING, callback=self.readyCallback)
        self.readyCallbackEnabled = True

    def disableReadyCallback(self):
        """
        HX711의 데이터 준비 콜백을 비활성화합니다.
        """
        GPIO.remove_event_detect(self.DOUT)
        self.paramCallback = None
        self.readyCallbackEnabled = False

    def setReadingFormat(self, byteFormat="MSB", bitFormat="MSB"):
        """
        읽기 형식을 설정합니다.
        byteFormat: 'MSB' 또는 'LSB'
        bitFormat: 'MSB' 또는 'LSB'
        """
        if byteFormat not in ['MSB', 'LSB']:
            raise ValueError(f"HX711::setReadingFormat() 잘못된 byteFormat: '{byteFormat}'")
        
        if bitFormat not in ['MSB', 'LSB']:
            raise ValueError(f"HX711::setReadingFormat() 잘못된 bitFormat: '{bitFormat}'")
        
        self.byteFormat = byteFormat
        self.bitFormat = bitFormat

    def convertFromTwosComplement24bit(self, inputValue):
        """
        24비트 2의 보수법 값을 부호 있는 정수로 변환합니다.
        """
        return -(inputValue & 0x800000) + (inputValue & 0x7FFFFF)

    def rawBytesToLong(self, rawBytes=None):
        """
        원시 바이트를 정수 값으로 변환합니다.
        """
        if rawBytes is None:
            return None

        # 3바이트를 합쳐 24비트 값을 만듦
        twosComplementValue = ((rawBytes[0] << 16) |
                               (rawBytes[1] << 8)  |
                               rawBytes[2])
        
        # 24비트 2의 보수법 값을 부호 있는 정수로 변환
        signed_int_value = self.convertFromTwosComplement24bit(twosComplementValue)

        # 마지막 값을 저장
        self.lastVal = signed_int_value

        return int(signed_int_value)

    def getLong(self, channel='A'):
        """
        특정 채널에서 읽은 데이터를 정수 값으로 반환합니다.
        """
        currentChannel = self.getChannel()
        if channel != currentChannel:
            self.setChannel(channel)
        
        rawBytes = self.readRawBytes()
        
        if channel != currentChannel:
            self.setChannel(currentChannel)
        
        if rawBytes is None:
            return None
        
        return self.rawBytesToLong(rawBytes)

    def setOffset(self, offset, channel='A'):
        """
        특정 채널의 오프셋 값을 설정합니다.
        offset: 설정할 오프셋 값
        channel: 'A' 또는 'B'
        """
        if channel == 'A':
            self.OFFSET_A = offset
            return True
        elif channel == 'B':
            self.OFFSET_B = offset
            return True
        
        raise ValueError(f"HX711::setOffset() 잘못된 채널: \"{channel}\"")

    def setOffsetA(self, offset):
        """
        채널 A의 오프셋 값을 설정합니다.
        """
        return self.setOffset(offset, 'A')

    def setOffsetB(self, offset):
        """
        채널 B의 오프셋 값을 설정합니다.
        """
        return self.setOffset(offset, 'B')

    def getOffset(self, channel='A'):
        """
        특정 채널의 오프셋 값을 반환합니다.
        """
        if channel == 'A':
            return self.OFFSET_A
        elif channel == 'B':
            return self.OFFSET_B
        
        raise ValueError(f"HX711::getOffset() 잘못된 채널: \"{channel}\"")

    def getOffsetA(self):
        """
        채널 A의 오프셋 값을 반환합니다.
        """
        return self.getOffset('A')

    def getOffsetB(self):
        """
        채널 B의 오프셋 값을 반환합니다.
        """
        return self.getOffset('B')
    
    def rawBytesToLongWithOffset(self, rawBytes=None, channel='A'):
        """
        원시 바이트를 오프셋을 적용한 정수 값으로 변환합니다.
        """
        if rawBytes is None:
            return None
        
        longValue = self.rawBytesToLong(rawBytes)
        offset = self.getOffset(channel)
        return longValue - offset

    def getLongWithOffset(self, channel='A'):
        """
        특정 채널에서 읽은 데이터를 오프셋을 적용한 정수 값으로 반환합니다.
        """
        currentChannel = self.getChannel()
        if channel != currentChannel:
            self.setChannel(channel)
        
        rawBytes = self.readRawBytes()
        
        if channel != currentChannel:
            self.setChannel(currentChannel)
        
        if rawBytes is None:
            return None
        
        return self.rawBytesToLongWithOffset(rawBytes, channel)

    def setReferenceUnit(self, referenceUnit, channel='A'):
        """
        특정 채널의 참조 단위를 설정합니다.
        referenceUnit: 설정할 참조 단위 값
        channel: 'A' 또는 'B'
        """
        if channel == 'A':
            self.REFERENCE_UNIT_A = referenceUnit
            return True
        elif channel == 'B':
            self.REFERENCE_UNIT_B = referenceUnit
            return True
        
        raise ValueError(f"HX711::setReferenceUnit() 잘못된 채널: \"{channel}\"")

    def getReferenceUnit(self, channel='A'):
        """
        특정 채널의 참조 단위를 반환합니다.
        """
        if channel == 'A':
            return self.REFERENCE_UNIT_A
        elif channel == 'B':
            return self.REFERENCE_UNIT_B
        
        raise ValueError(f"HX711::getReferenceUnit() 잘못된 채널: \"{channel}\"")

    def rawBytesToWeight(self, rawBytes=None, channel='A'):
        """
        원시 바이트를 무게 값으로 변환합니다.
        """
        if rawBytes is None:
            return None
        
        # 오프셋을 적용한 정수 값으로 변환
        longWithOffset = self.rawBytesToLongWithOffset(rawBytes, channel)
        
        # 채널에 따라 참조 단위를 선택
        if channel == 'A':
            referenceUnit = self.REFERENCE_UNIT_A
        elif channel == 'B':
            referenceUnit = self.REFERENCE_UNIT_B
        else:
            raise ValueError(f"HX711::rawBytesToWeight() 잘못된 채널: \"{channel}\"")
        
        if referenceUnit == 0:
            raise ValueError("HX711::rawBytesToWeight() 참조 단위가 0입니다. 0으로 나눌 수 없습니다!")
        
        # 참조 단위를 나눠 실제 무게 값으로 변환
        return longWithOffset / referenceUnit

    def getWeight(self, channel='A'):
        """
        특정 채널에서 읽은 데이터를 무게 값으로 반환합니다.
        """
        currentChannel = self.getChannel()
        if channel != currentChannel:
            self.setChannel(channel)
        
        rawBytes = self.readRawBytes()
        
        if channel != currentChannel:
            self.setChannel(currentChannel)
        
        if rawBytes is None:
            return None
        
        return self.rawBytesToWeight(rawBytes, channel)

    def autosetOffset(self, channel='A'):
        """
        자동으로 오프셋 값을 설정합니다.
        """
        currentReferenceUnit = self.getReferenceUnit(channel)
        
        # 참조 단위를 1로 설정하여 원시 값을 직접 읽음
        self.setReferenceUnit(1, channel)
        
        currentChannel = self.getChannel()
        if channel != currentChannel:
            self.setChannel(channel)
            
        # 현재 원시 값을 오프셋으로 설정
        newOffsetValue = self.getLong(channel)
        
        self.setOffset(newOffsetValue, channel)
        
        # 원래 참조 단위로 복구
        self.setReferenceUnit(currentReferenceUnit, channel)
        
        if channel != currentChannel:
            self.setChannel(currentChannel)
        
        return True

# EOF - hx711.py
