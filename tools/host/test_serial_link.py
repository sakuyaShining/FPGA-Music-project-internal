"""串口异常、短写和回读地址验证；用假串口对象覆盖故障路径。"""
import unittest
from unittest.mock import Mock
from serial_link import SerialLink
import dsp_host as dh


class SerialLinkTests(unittest.TestCase):
    def setUp(self):
        self.link = SerialLink("unused-test-port")
        self.link.ser = Mock(timeout=.5)
        self.link.ser.write.return_value = 2

    def test_response_address_must_match_request(self):
        self.link.ser.read.return_value = bytes([0x60, 0x99])
        self.assertIsNone(self.link.read_reg(0x61))
        self.link.ser.read.return_value = bytes([0x61, 0x23])
        self.assertEqual(self.link.read_reg(0x61), 0x23)

    def test_failed_read_restores_timeout(self):
        self.link.ser.read.side_effect = OSError("断线")
        self.assertIsNone(self.link.read_reg(0x61, timeout=.01))
        self.assertEqual(self.link.ser.timeout, .5)

    def test_partial_write_is_failure(self):
        self.link.ser.write.return_value = 1
        with self.assertRaises(OSError):
            self.link.send(dh.cmd_note("on:60:12"))
        self.link.ser.flush.assert_not_called()


if __name__ == "__main__":
    unittest.main()
