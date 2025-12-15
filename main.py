import time
import pysoem

# 1. 创建主站并扫描网络
master = pysoem.Master()

adapters = pysoem.find_adapters()
for adapter in adapters:
        print(f"Name: {adapter.name}")
        print(f"Desc: {adapter.desc}")
        print("---")

master.open(r'\Device\NPF_{C36DFD74-806B-41E9-8089-D59ED008E09D}') # 请替换为你的网卡名称，网卡名称从上面的输出找
master.config_init()

# 2. 检查找到的从站（你的IO模块），如果只有一个模块就只有1个slave，如果把阀岛插到伺服的后面，slave就有2个，第一个伺服，第二个阀岛
if len(master.slaves) > 0:
    io_module = master.slaves[0]
    print(f"Found IO module: {io_module.name}")
    # 3. 配置从站（SDO在此阶段使用）
    # 示例：通过SDO读取一个对象字典条目，比如厂商ID (0x1018:0x01)
    try:
        vendor_id = io_module.sdo_read(0x1018, 0x01)
        # 将 bytes 转换为整数（假设为小端序，这是EtherCAT的常见格式）
        vendor_id_int = int.from_bytes(vendor_id, byteorder='little', signed=False)
        print(f"Vendor ID: 0x{vendor_id_int:08X}") # 以8位十六进制数，前导0格式打印
    except pysoem.SdoError as e:
        print(f"SDO read failed: {e}")

    # 4. 映射PDO（配置哪些IO数据进入过程数据映像）
    master.config_map()

    #切换到“预运行状态”（此状态允许SDO配置）
    master.state = pysoem.PREOP_STATE
    master.write_state() # 写入状态
    time.sleep(0.1) # 短暂延时
    master.state_check(pysoem.PREOP_STATE) # 检查所有从站是否达到该状态
    print(f"Current state after PRE-OP request: {master.state_check(pysoem.PREOP_STATE, timeout=50_000):#x}")

    #启动之前可以通过SDO配置参数
    #io_module.sdo_write(0x2000,0x01,(0xff).to_bytes(1, byteorder='little', signed=False))

    # 3. 切换到“安全运行状态”（此状态允许输出PDO）
    print("Setting state to SAFE-OP...")
    master.state = pysoem.SAFEOP_STATE
    master.write_state()
    time.sleep(0.1)

    print(f"Current state after SAFE-OP request: {master.state_check(pysoem.SAFEOP_STATE, timeout=50_000):#x}")

    # 4. 切换到最终的“运行状态”（允许输入和输出PDO）
    print("Setting state to OP...")
    master.state = pysoem.OP_STATE
    master.write_state()
    time.sleep(0.1)

    # 使用 state_check 确认所有从站已进入 OP 状态
    op_state_check = master.state_check(pysoem.OP_STATE, timeout=2000_000)
    if op_state_check == pysoem.OP_STATE:
        print("All slaves successfully reached OPERATIONAL state.")
    else:
        print(f"WARNING: Not all slaves reached OP state. State code: {op_state_check:#x}")
        # 这里可以添加更详细的诊断，例如检查每个从站的 AL 状态码
   
    #outputbyte这个字节对应8个阀，每个bit是一个阀
    outputbyte=0x1
    # 7. 主循环：周期性读写PDO数据
    try:
        while True:

             # 1. 将 output 转换为可变的 bytearray
            output_data = bytearray(io_module.output)
            # 2. 修改 bytearray 的内容
            output_data[0] =outputbyte  # 假设 output_byte 是一个 0-255 之间的整数
            # 3. 将修改后的数据重新赋给 io_module.output
            io_module.output = bytes(output_data)

            # 发送过程数据（输出）
            master.send_processdata()
            # 接收过程数据（输入）
            master.receive_processdata(timeout=2_000_000)
           
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        # 8. 退出前，将主站状态切回初始化
        master.state = pysoem.INIT_STATE

else:
    print("No slaves found.")
master.close()