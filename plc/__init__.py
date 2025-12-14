"""
PLC Communication Module
========================

Module giao tiếp với PLC Siemens S7 qua Snap7.

Public API:
- PLCClient: Kết nối và giao tiếp với PLC
- AlarmManager: Quản lý trạng thái báo động
- AlarmConfig: Cấu hình địa chỉ báo động
"""

from .plc_client import PLCClient, PLCConnectionState
from .alarm_manager import AlarmManager, AlarmType, AlarmState, AlarmConfig

__all__ = [
    'PLCClient',
    'PLCConnectionState',
    'AlarmManager',
    'AlarmType',
    'AlarmState',
    'AlarmConfig',
]

