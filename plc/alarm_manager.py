"""
Alarm Manager Module
====================

Quản lý trạng thái báo động và gửi tín hiệu đến PLC.

Features:
- Quản lý trạng thái ON/OFF cho từng loại báo động
- Tránh gửi tín hiệu trùng lặp
- Callback khi trạng thái thay đổi
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable, Dict
import time

from .plc_client import PLCClient


class AlarmType(Enum):
    """Loại báo động"""
    PERSON = "person"  # Báo động người vào vùng nguy hiểm
    COAL = "coal"  # Báo động tắc than


class AlarmState(Enum):
    """Trạng thái báo động"""
    OFF = False
    ON = True


@dataclass
class AlarmConfig:
    """Cấu hình địa chỉ báo động trong PLC"""
    db_number: int
    byte_offset: int
    bit_offset: int
    
    def __str__(self) -> str:
        return f"DB{self.db_number}.DBX{self.byte_offset}.{self.bit_offset}"


class AlarmManager:
    """
    Quản lý báo động và gửi tín hiệu đến PLC
    
    Features:
    - Quản lý nhiều loại báo động
    - Tránh gửi tín hiệu trùng lặp
    - Callback khi trạng thái thay đổi
    - Logging
    
    Usage:
        manager = AlarmManager(
            plc_client=client,
            person_alarm=AlarmConfig(db=300, byte=6, bit=0),
            coal_alarm=AlarmConfig(db=300, byte=6, bit=1),
            on_alarm_change=lambda type, state: print(f"{type}: {state}")
        )
        
        # Bật báo động
        manager.set_alarm(AlarmType.PERSON, AlarmState.ON)
        
        # Tắt báo động
        manager.set_alarm(AlarmType.PERSON, AlarmState.OFF)
        
        # Tắt tất cả
        manager.turn_off_all()
    """
    
    def __init__(
        self,
        plc_client: PLCClient,
        person_alarm: Optional[AlarmConfig] = None,
        coal_alarm: Optional[AlarmConfig] = None,
        on_alarm_change: Optional[Callable[[AlarmType, AlarmState], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            plc_client: PLC client để gửi tín hiệu
            person_alarm: Cấu hình địa chỉ báo động người
            coal_alarm: Cấu hình địa chỉ báo động than
            on_alarm_change: Callback khi trạng thái báo động thay đổi
            on_error: Callback khi có lỗi
        """
        self.plc_client = plc_client
        self.on_alarm_change = on_alarm_change
        self.on_error = on_error
        
        # Cấu hình địa chỉ
        self._alarm_configs: Dict[AlarmType, AlarmConfig] = {}
        if person_alarm:
            self._alarm_configs[AlarmType.PERSON] = person_alarm
        if coal_alarm:
            self._alarm_configs[AlarmType.COAL] = coal_alarm
        
        # Trạng thái hiện tại
        self._alarm_states: Dict[AlarmType, AlarmState] = {
            AlarmType.PERSON: AlarmState.OFF,
            AlarmType.COAL: AlarmState.OFF,
        }
        
        # Thời gian thay đổi cuối
        self._last_change_time: Dict[AlarmType, float] = {}
    
    def get_alarm_state(self, alarm_type: AlarmType) -> AlarmState:
        """Lấy trạng thái báo động hiện tại"""
        return self._alarm_states.get(alarm_type, AlarmState.OFF)
    
    def set_alarm(self, alarm_type: AlarmType, state: AlarmState) -> bool:
        """Đặt trạng thái báo động
        
        Args:
            alarm_type: Loại báo động
            state: Trạng thái mới
            
        Returns:
            True nếu gửi tín hiệu thành công
        """
        current_state = self._alarm_states.get(alarm_type, AlarmState.OFF)
        
        # Không gửi nếu trạng thái không thay đổi
        if current_state == state:
            return True
        
        # Lấy config
        config = self._alarm_configs.get(alarm_type)
        if not config:
            self._report_error(f"Không có cấu hình cho báo động {alarm_type.value}")
            return False
        
        # Gửi tín hiệu đến PLC
        success = self._send_to_plc(config, state.value)
        
        if success:
            self._alarm_states[alarm_type] = state
            self._last_change_time[alarm_type] = time.time()
            
            # Gọi callback
            if self.on_alarm_change:
                try:
                    self.on_alarm_change(alarm_type, state)
                except:
                    pass
        
        return success
    
    def _send_to_plc(self, config: AlarmConfig, value: bool) -> bool:
        """Gửi tín hiệu đến PLC"""
        if not self.plc_client.is_connected:
            # Thử reconnect
            if not self.plc_client.health_check():
                self._report_error("PLC không kết nối")
                return False
        
        success = self.plc_client.write_bit(
            config.db_number,
            config.byte_offset,
            config.bit_offset,
            value
        )
        
        if not success:
            # Thử reconnect và gửi lại
            if self.plc_client.reconnect():
                success = self.plc_client.write_bit(
                    config.db_number,
                    config.byte_offset,
                    config.bit_offset,
                    value
                )
        
        return success
    
    def turn_on_person_alarm(self) -> bool:
        """Bật báo động người"""
        return self.set_alarm(AlarmType.PERSON, AlarmState.ON)
    
    def turn_off_person_alarm(self) -> bool:
        """Tắt báo động người"""
        return self.set_alarm(AlarmType.PERSON, AlarmState.OFF)
    
    def turn_on_coal_alarm(self) -> bool:
        """Bật báo động than"""
        return self.set_alarm(AlarmType.COAL, AlarmState.ON)
    
    def turn_off_coal_alarm(self) -> bool:
        """Tắt báo động than"""
        return self.set_alarm(AlarmType.COAL, AlarmState.OFF)
    
    def turn_off_all(self) -> bool:
        """Tắt tất cả báo động
        
        Returns:
            True nếu tắt tất cả thành công
        """
        success = True
        
        for alarm_type in self._alarm_configs.keys():
            if self._alarm_states.get(alarm_type) == AlarmState.ON:
                if not self.set_alarm(alarm_type, AlarmState.OFF):
                    success = False
        
        return success
    
    def reset(self) -> None:
        """Reset tất cả trạng thái (không gửi tín hiệu)"""
        for alarm_type in self._alarm_states.keys():
            self._alarm_states[alarm_type] = AlarmState.OFF
        self._last_change_time.clear()
    
    def get_state_summary(self) -> Dict[str, any]:
        """Lấy tóm tắt trạng thái"""
        return {
            "person_alarm": self._alarm_states.get(AlarmType.PERSON, AlarmState.OFF).name,
            "coal_alarm": self._alarm_states.get(AlarmType.COAL, AlarmState.OFF).name,
            "plc_connected": self.plc_client.is_connected,
            "person_config": str(self._alarm_configs.get(AlarmType.PERSON, "N/A")),
            "coal_config": str(self._alarm_configs.get(AlarmType.COAL, "N/A")),
        }
    
    def _report_error(self, message: str) -> None:
        """Báo lỗi qua callback"""
        if self.on_error:
            try:
                self.on_error(message)
            except:
                pass
    
    def update_config(self, alarm_type: AlarmType, config: AlarmConfig) -> None:
        """Cập nhật cấu hình địa chỉ báo động"""
        self._alarm_configs[alarm_type] = config
    
    @property
    def is_any_alarm_on(self) -> bool:
        """Kiểm tra có báo động nào đang bật không"""
        return any(state == AlarmState.ON for state in self._alarm_states.values())
    
    @property
    def person_alarm_state(self) -> AlarmState:
        """Trạng thái báo động người"""
        return self._alarm_states.get(AlarmType.PERSON, AlarmState.OFF)
    
    @property
    def coal_alarm_state(self) -> AlarmState:
        """Trạng thái báo động than"""
        return self._alarm_states.get(AlarmType.COAL, AlarmState.OFF)

