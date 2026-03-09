import socket
import time

# 江苏卫视HD 的配置
MCAST_GRP = '232.0.1.140'
MCAST_PORT = 1140
BIND_IP = '10.178.41.1' # 你的 IPTV 网卡

def start_sim():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # 绑定物理网卡发送
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(BIND_IP))
    # 设置 TTL
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    print(f"正在模拟【江苏卫视HD】流...")
    print(f"地址: {MCAST_GRP}:{MCAST_PORT} | 网卡: {BIND_IP}")
    
    try:
        count = 0
        while True:
            # 模拟一个稍微大一点的数据包，模仿视频流
            data = ("江苏卫视数据包_" + str(count) + "_" + "X"*1000).encode()
            sock.sendto(data, (MCAST_GRP, MCAST_PORT))
            count += 1
            if count % 20 == 0:
                print(f"已发送 {count} 个视频切片...")
            time.sleep(0.05) # 模拟约 200kbps 的低码率流
    except KeyboardInterrupt:
        print("\n已停止测试")
    finally:
        sock.close()

if __name__ == "__main__":
    start_sim()