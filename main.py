from pyb import Pin, Timer, ExtInt
import time
from machine import I2C, Pin
import ssd1306
#231
# ========== OLED 显示屏 ==========
i2c = I2C(sda=Pin("PB12"), scl=Pin("PB13"))
oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# ========== A0启动按键 ==========
start_flag = False

def key_isr(line):
    global start_flag
    start_flag = True

# PA0上拉输入，按下接地触发中断
key_pin = Pin('PA0', Pin.IN, Pin.PULL_UP)
ext = ExtInt(key_pin, ExtInt.IRQ_FALLING, Pin.PULL_UP, key_isr)

# ========== 电机引脚 ==========
motor1 = Pin("PB6", Pin.OUT)  # 右前 1
motor2 = Pin("PB7", Pin.OUT)  # 左前 2
motor3 = Pin("PB8", Pin.OUT)  # 左后 3
motor4 = Pin("PB9", Pin.OUT)  # 右后 4

tim4 = Timer(4, freq=50)
ch1 = tim4.channel(1, Timer.PWM, pin=motor1, pulse_width_percent=0)
ch2 = tim4.channel(2, Timer.PWM, pin=motor2, pulse_width_percent=0)
ch3 = tim4.channel(3, Timer.PWM, pin=motor3, pulse_width_percent=0)
ch4 = tim4.channel(4, Timer.PWM, pin=motor4, pulse_width_percent=0)

# ========== 基础动作 ==========
def go():
    ch1.pulse_width_percent(30)
    ch2.pulse_width_percent(30)
    ch3.pulse_width_percent(30)
    ch4.pulse_width_percent(30)

def stop():
    ch1.pulse_width_percent(0)
    ch2.pulse_width_percent(0)
    ch3.pulse_width_percent(0)
    ch4.pulse_width_percent(0)

# 左转偏航（向左前方斜）
def turn_right_bias():
    ch1.pulse_width_percent(30)
    ch2.pulse_width_percent(0)
    ch3.pulse_width_percent(0)
    ch4.pulse_width_percent(30)

# 右转偏航（向右前方斜）
def turn_left_bias():
    ch1.pulse_width_percent(0)
    ch2.pulse_width_percent(30)
    ch3.pulse_width_percent(30)
    ch4.pulse_width_percent(0)

# 原地回正（四轮同速，恢复直走姿态）
def go_straight():
    go()

# ========== 蜂鸣器 PA8 ==========
tim1 = Timer(1, prescaler=72, period=500)
buz = tim1.channel(1, Timer.PWM, pin=Pin('PA8'))
buz.pulse_width_percent(0)

# ========== 超声波 PB3 PB4 ==========
trig = Pin("PB3", Pin.OUT)
echo = Pin("PB4", Pin.IN, Pin.PULL_DOWN)
trig.low()
time.sleep_ms(200)

def get_dist():
    trig.high()
    time.sleep_us(20)
    trig.low()

    start = time.ticks_us()
    t1 = start
    while echo.value() == 0:
        t1 = time.ticks_us()
        if time.ticks_diff(t1, start) > 30000:
            return 999

    t2 = t1
    while echo.value() == 1:
        t2 = time.ticks_us()
        if time.ticks_diff(t2, start) > 30000:
            return 999

    d = (t2 - t1) * 0.034 / 2
    if d < 2 or d > 120:
        return 999
    return round(d, 1)

# ========== 舵机 PB10 ==========
tim2 = Timer(2, freq=50)
servo = tim2.channel(3, Timer.PWM, pin=Pin("PB10"))

def servo_center():
    servo.pulse_width_percent(7.5)
    time.sleep_ms(700)

def servo_left90():
    servo.pulse_width_percent(7.3)
    time.sleep_ms(630)

def servo_right90():
    servo.pulse_width_percent(7.7)
    time.sleep_ms(700)

def scan_fixed():
    servo_center()
    servo_left90()
    servo_right90()
    servo_right90()
    servo_left90()
    servo_center()

# ====================== 红外避障 ======================
# 接线：红外 OUT → PB5
ir_pin = Pin("PB5", Pin.IN)

# 红外模块逻辑：灯亮=有障碍=输出0，灯暗=无障碍=输出1
def ir_has_obstacle():
    return ir_pin.value() == 0  # 灯亮（有障碍）返回True

# ====================== 等待按键启动 ======================
oled.fill(0)
oled.text("Press PA0 Start", 0, 20)
oled.show()
print("等待按下PA0按键启动小车...")

while not start_flag:
    time.sleep_ms(20)

# 启动提示音
buz.pulse_width_percent(40)
time.sleep_ms(100)
buz.pulse_width_percent(0)

# ====================== 主程序流程 ======================
print("=== 按顺序执行：直走 → 左偏 → 直走 → 右回正 → 右偏 → 直走 → 遇障停下 → 回正 → 直走 ===")
servo_center()

# 1. 直走，检测第一个障碍物
print("1. 直走，找第一个障碍物")
go()
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    oled.fill(0)
    oled.text("Step 1: Straight", 0,0)
    oled.text("Dist: {}cm".format(dis),0,20)
    oled.text("IR: {}".format(ir_val),0,40)
    oled.text("Light ON=Stop",0,55)
    oled.show()

    # 超声波<12cm 或 红外灯亮(有障碍=0) → 停车
    if (dis != 999 and dis < 12) or ir_has_obstacle():
        stop()
        buz.pulse_width_percent(50)
        time.sleep_ms(100)
        buz.pulse_width_percent(0)
        print("检测到障碍，停车")
        break
    time.sleep_ms(100)

# 等待障碍物移除
print("请拿走障碍物...")
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    if (dis == 999 or dis > 20) and not ir_has_obstacle():
        print("已移除，继续")
        break
    time.sleep_ms(100)

scan_fixed()

# 2. 向左偏转
print("2. 向左偏转，斜向前进")
turn_left_bias()
time.sleep_ms(250)
go_straight()

# 4. 直走检测第二个障碍物
print("4. 直走，找第二个障碍物")
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    oled.fill(0)
    oled.text("Step 4: Straight",0,0)
    oled.text("Dist: {}cm".format(dis),0,20)
    oled.text("IR: {}".format(ir_val),0,40)
    oled.text("Light ON=Stop",0,55)
    oled.show()

    if (dis != 999 and dis < 12) or ir_has_obstacle():
        stop()
        buz.pulse_width_percent(50)
        time.sleep_ms(100)
        buz.pulse_width_percent(0)
        print("检测到障碍，停车")
        break
    time.sleep_ms(100)

# 等待障碍物移除
print("请拿走障碍物...")
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    if (dis == 999 or dis > 20) and not ir_has_obstacle():
        print("已移除，继续")
        break
    time.sleep_ms(100)

scan_fixed()
servo.pulse_width_percent(7.3)
time.sleep_ms(100)
servo.pulse_width_percent(7.5)
time.sleep_ms(700)

# 右转偏航
print("2. 向右偏转，斜向前进")
turn_right_bias()
time.sleep_ms(630)
go_straight()

# 5. 回正直走
print("5. 回正，直走前进")
go_straight()
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    oled.fill(0)
    oled.text("Step 5: Straight",0,0)
    oled.text("Dist: {}cm".format(dis),0,20)
    oled.text("IR: {}".format(ir_val),0,40)
    oled.text("Light ON=Stop",0,55)
    oled.show()

    if (dis != 999 and dis < 12) or ir_has_obstacle():
        stop()
        buz.pulse_width_percent(50)
        time.sleep_ms(100)
        buz.pulse_width_percent(0)
        print("检测到障碍，停车")
        break
    time.sleep_ms(100)

# 等待障碍物移除
print("请拿走障碍物...")
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    if (dis == 999 or dis > 20) and not ir_has_obstacle():
        print("已移除，继续")
        break
    time.sleep_ms(100)

# 最后左偏回正
print("最后：向左偏转斜走再直走")
turn_left_bias()
time.sleep_ms(330)
go_straight()

# 最终直走
print("最终直走模式：灯亮停，灯暗走")
while True:
    dis = get_dist()
    ir_val = ir_pin.value()
    oled.fill(0)
    oled.text("FINAL: Straight",0,0)
    oled.text("Dist: {}cm".format(dis),0,20)
    oled.text("IR: {}".format(ir_val),0,40)
    oled.text("Light OFF=Go",0,55)
    oled.show()

    # 红外灯亮（有障碍=0）或 超声波近 → 停车
    if (dis != 999 and dis < 12) or ir_has_obstacle():
        stop()
    else:
        go()

    time.sleep_ms(100)
