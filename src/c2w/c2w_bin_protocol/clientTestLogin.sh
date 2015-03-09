#!/bin/bash
mv client_protocol.py client_protocol_tmp.py;
mv client_protocolMax.py client_protocol.py;
trial c2w_test.c2w_client_test.ClientTestCase.test_login;
mv client_protocol.py client_protocolMax.py;
mv client_protocol_tmp.py client_protocol.py;