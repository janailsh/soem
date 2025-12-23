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
    

    # 1. 首先切换到“预运行状态”，才能进行SDO配置
    master.state = pysoem.PREOP_STATE
    master.write_state()
    master.state_check(pysoem.PREOP_STATE, timeout=50_000)

    print("Switched to PREOP state for configuration.")

    # 2. 执行SDO写入，配置模块的PDO（即图片中的表格）
    print("Configuring IO module PDO via SDO...")
    config_list = [
    # ---------- 通信 / 安全 ----------
    (0xF800, 1, 0x00, 1),
    (0xF800, 2, 0x00, 1),
    (0xF800, 3, 0x01, 1),
    (0xF800, 4, 0x00, 1),

    # ---------- 同步模式 ----------
    #(0x1C32, 1, 0x0000, 2),
    #(0x1C33, 1, 0x0000, 2),

    # ---------- RxPDO Assign ----------
 #   (0x1C12, 0, 0x00, 1),
  #  (0x1C12, 1, 0x17A0, 2),
  #  (0x1C12, 0, 0x01, 1),

    # ---------- TxPDO Assign ----------
  #  (0x1C13, 0, 0x00, 1),
  #  (0x1C13, 1, 0x1BA0, 2),
  #  (0x1C13, 2, 0x1A01, 2),
  #  (0x1C13, 0, 0x02, 1),

    # ---------- DI 滤波 ----------
    (0x8000, 1, 0x0400, 2),
    (0x8000, 2, 0x0400, 2),

    # ---------- PDO 映射 ----------
    (0xF030, 0, 0x00, 1),
    (0xF030, 1, 0x10F41010, 4),
    (0xF030, 0, 0x01, 1),
    ]

    for idx, subidx, data, length in config_list:
        try:

            # 将整数转换为字节（小端序）
            data_bytes = data.to_bytes(length, byteorder='little')
            io_module.sdo_write(idx, subidx, data_bytes)
            print(f"  Success: Wrote 0x{data:X} to 0x{idx:X}:{subidx}")
        except pysoem.SdoError as e:
            print(f"  Failed to write to 0x{idx:X}:{subidx}: {e}")

    master.config_map()

    # 4. 现在！才能访问 inputs / outputs
    for i, slave in enumerate(master.slaves):
        print(f"Slave {i}:")
        print(f"  outputs len = {len(slave.output)} bytes")
        print(f"  inputs  len = {len(slave.input)} bytes")
  
    # 4. 尝试切换到安全运行状态，然后运行状态
    master.state = pysoem.SAFEOP_STATE
    master.write_state()
    master.state_check(pysoem.SAFEOP_STATE, timeout=50_000)
    print("Switched to SAFEOP state.")

    master.state = pysoem.OP_STATE
    master.write_state()
    master.state_check(pysoem.OP_STATE, timeout=50_000)
    print("Switched to OP state. Cyclic data exchange ready.")
    # 7. 主循环：周期性读写PDO数据
    cycle = 0
    try:
        while True:

            master.send_processdata()
            master.receive_processdata(2000)
            cycle += 1
            if cycle % 10 == 0:
                io = master.slaves[0]

                out_hex = io.output.hex(" ")
                in_hex  = io.input.hex(" ")
                print(
                    f"[Cycle {cycle}] "
                    f"OUT({len(io.output)}B): {out_hex} | "
                    f"IN({len(io.input)}B): {in_hex}"
                )

            time.sleep(0.01)  # 尽量短

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        # 8. 退出前，将主站状态切回初始化
        master.state = pysoem.INIT_STATE

else:
    print("No slaves found.")
master.close()