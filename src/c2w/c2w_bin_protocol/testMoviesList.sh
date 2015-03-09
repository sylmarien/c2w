#!/bin/bash
mv server_protocol.py server_protocol_tmp.py;
mv server_protocolMax.py server_protocol.py;
trial c2w_test.c2w_server_test.ServerTestCase.test_movielist;
mv server_protocol.py server_protocolMax.py;
mv server_protocol_tmp.py server_protocol.py;