"""
PLC Client Module
=================

Kết nối và giao tiếp với PLC Siemens S7-300/400 qua Snap7.

Features:
- Auto reconnect
- Thread-safe operations
- Health check
- Bit-level read/write
"""

import threading
import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

try:
    import snap7
    from snap7.util import set_bool, get_bool
    SNAP7_AVAILABLE = True
except ImportError:
    SNAP7_AVAILABLE = False
    print("Warning: snap7 not installed. PLC communication will be disabled.")


class PLCConnectionState(Enum):
    """Trạng thái kết nối PLC"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class PLCConnectionConfig:
    """Cấu hình kết nối PLC"""
    ip: str = "192.168.0.4"
    port: int = 102
    rack: int = 0
    slot: int = 2
    
    def __str__(self) -> str:
        return f"PLC({self.ip}, rack={self.rack}, slot={self.slot})"


class PLCClient:
    """
    Client giao tiếp với PLC Siemens S7
    
    Features:
    - Thread-safe
    - Auto reconnect với backoff
    - Health check định kỳ
    - Callback khi trạng thái thay đổi
    
    Usage:
        client = PLCClient(
            ip="192.168.0.4",
            rack=0,
            slot=2,
            on_state_change=lambda state: print(state)
        )
        
        # Kết nối
        if client.connect():
            # Ghi bit
            client.write_bit(db=300, byte=6, bit=0, value=True)
            
            # Đọc bit
            value = client.read_bit(db=300, byte=6, bit=0)
        
        # Ngắt kết nối
        client.disconnect()
    """
    
    def __init__(
        self,
        ip: str = "192.168.0.4",
        rack: int = 0,
        slot: int = 2,
        max_reconnect_attempts: int = 3,
        reconnect_interval: float = 1.0,
        health_check_interval: float = 10.0,
        on_state_change: Optional[Callable[[PLCConnectionState], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            ip: Địa chỉ IP của PLC
            rack: Rack number
            slot: Slot number
            max_reconnect_attempts: Số lần reconnect tối đa
            reconnect_interval: Thời gian chờ giữa các lần reconnect (giây)
            health_check_interval: Khoảng thời gian kiểm tra kết nối (giây)
            on_state_change: Callback khi trạng thái thay đổi
            on_error: Callback khi có lỗi
        """
        self.config = PLCConnectionConfig(ip=ip, rack=rack, slot=slot)
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_interval = reconnect_interval
        self.health_check_interval = health_check_interval
        self.on_state_change = on_state_change
        self.on_error = on_error
        
        # Internal state
        self._client = None
        self._state = PLCConnectionState.DISCONNECTED
        self._lock = threading.Lock()
        self._reconnect_count = 0
        self._last_health_check = 0.0
        self._enabled = True
    
    @property
    def state(self) -> PLCConnectionState:
        """Trạng thái kết nối hiện tại"""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Kiểm tra đã kết nối chưa"""
        return self._state == PLCConnectionState.CONNECTED
    
    def connect(self) -> bool:
        """Kết nối đến PLC
        
        Returns:
            True nếu kết nối thành công
        """
        if not SNAP7_AVAILABLE:
            self._report_error("snap7 library not available")
            return False
        
        if not self._enabled:
            return False
        
        with self._lock:
            self._set_state(PLCConnectionState.CONNECTING)
            
            try:
                # Tạo client mới
                if self._client is not None:
                    try:
                        self._client.disconnect()
                    except:
                        pass
                
                self._client = snap7.client.Client()
                self._client.connect(
                    self.config.ip, 
                    self.config.rack, 
                    self.config.slot
                )
                
                if self._client.get_connected():
                    self._set_state(PLCConnectionState.CONNECTED)
                    self._reconnect_count = 0
                    return True
                else:
                    self._set_state(PLCConnectionState.ERROR)
                    self._report_error(f"Không thể kết nối PLC: {self.config}")
                    return False
                    
            except Exception as e:
                self._set_state(PLCConnectionState.ERROR)
                self._report_error(f"Lỗi kết nối PLC: {str(e)}")
                return False
    
    def disconnect(self) -> None:
        """Ngắt kết nối PLC"""
        with self._lock:
            if self._client is not None:
                try:
                    self._client.disconnect()
                except:
                    pass
                self._client = None
            
            self._set_state(PLCConnectionState.DISCONNECTED)
    
    def reconnect(self) -> bool:
        """Thử kết nối lại
        
        Returns:
            True nếu reconnect thành công
        """
        if self._reconnect_count >= self.max_reconnect_attempts:
            self._report_error(f"Đã vượt quá số lần reconnect tối đa ({self.max_reconnect_attempts})")
            return False
        
        self._reconnect_count += 1
        self._set_state(PLCConnectionState.RECONNECTING)
        
        # Đóng kết nối cũ
        with self._lock:
            if self._client is not None:
                try:
                    self._client.disconnect()
                except:
                    pass
                self._client = None
        
        time.sleep(self.reconnect_interval)
        
        # Thử kết nối lại
        return self.connect()
    
    def check_connection(self) -> bool:
        """Kiểm tra kết nối thực tế
        
        Returns:
            True nếu đang kết nối
        """
        with self._lock:
            if self._client is None:
                if self._state == PLCConnectionState.CONNECTED:
                    self._set_state(PLCConnectionState.DISCONNECTED)
                return False
            
            try:
                connected = self._client.get_connected()
                if not connected and self._state == PLCConnectionState.CONNECTED:
                    self._set_state(PLCConnectionState.DISCONNECTED)
                return connected
            except:
                if self._state == PLCConnectionState.CONNECTED:
                    self._set_state(PLCConnectionState.ERROR)
                return False
    
    def health_check(self) -> bool:
        """Kiểm tra sức khỏe kết nối định kỳ
        
        Returns:
            True nếu kết nối OK hoặc đã reconnect thành công
        """
        current_time = time.time()
        
        if current_time - self._last_health_check < self.health_check_interval:
            return self.is_connected
        
        self._last_health_check = current_time
        
        if not self.check_connection():
            # Thử reconnect
            if self._reconnect_count < self.max_reconnect_attempts:
                return self.reconnect()
            else:
                # Reset counter sau một thời gian
                if self._reconnect_count >= self.max_reconnect_attempts * 2:
                    self._reconnect_count = 0
                return False
        
        return True
    
    def read_byte(self, db_number: int, byte_offset: int) -> Optional[int]:
        """Đọc 1 byte từ DB
        
        Args:
            db_number: Số DB
            byte_offset: Offset byte
            
        Returns:
            Giá trị byte hoặc None nếu lỗi
        """
        if not self.is_connected:
            return None
        
        with self._lock:
            try:
                data = self._client.db_read(db_number, byte_offset, 1)
                return data[0]
            except Exception as e:
                self._report_error(f"Lỗi đọc DB{db_number}.DBB{byte_offset}: {str(e)}")
                self._set_state(PLCConnectionState.ERROR)
                return None
    
    def write_byte(self, db_number: int, byte_offset: int, value: int) -> bool:
        """Ghi 1 byte vào DB
        
        Args:
            db_number: Số DB
            byte_offset: Offset byte
            value: Giá trị (0-255)
            
        Returns:
            True nếu thành công
        """
        if not self.is_connected:
            return False
        
        with self._lock:
            try:
                data = bytearray([value & 0xFF])
                self._client.db_write(db_number, byte_offset, data)
                return True
            except Exception as e:
                self._report_error(f"Lỗi ghi DB{db_number}.DBB{byte_offset}: {str(e)}")
                self._set_state(PLCConnectionState.ERROR)
                return False
    
    def read_bit(self, db_number: int, byte_offset: int, bit_offset: int) -> Optional[bool]:
        """Đọc 1 bit từ DB
        
        Args:
            db_number: Số DB
            byte_offset: Offset byte
            bit_offset: Offset bit (0-7)
            
        Returns:
            Giá trị bit hoặc None nếu lỗi
        """
        if not self.is_connected or not SNAP7_AVAILABLE:
            return None
        
        with self._lock:
            try:
                data = self._client.db_read(db_number, byte_offset, 1)
                return get_bool(data, 0, bit_offset)
            except Exception as e:
                self._report_error(f"Lỗi đọc DB{db_number}.DBX{byte_offset}.{bit_offset}: {str(e)}")
                self._set_state(PLCConnectionState.ERROR)
                return None
    
    def write_bit(self, db_number: int, byte_offset: int, 
                  bit_offset: int, value: bool) -> bool:
        """Ghi 1 bit vào DB
        
        Args:
            db_number: Số DB
            byte_offset: Offset byte
            bit_offset: Offset bit (0-7)
            value: Giá trị (True/False)
            
        Returns:
            True nếu thành công
        """
        if not self.is_connected or not SNAP7_AVAILABLE:
            return False
        
        with self._lock:
            try:
                # Đọc byte hiện tại
                data = self._client.db_read(db_number, byte_offset, 1)
                # Thiết lập bit
                set_bool(data, 0, bit_offset, value)
                # Ghi lại
                self._client.db_write(db_number, byte_offset, data)
                return True
            except Exception as e:
                self._report_error(f"Lỗi ghi DB{db_number}.DBX{byte_offset}.{bit_offset}: {str(e)}")
                self._set_state(PLCConnectionState.ERROR)
                return False
    
    def _set_state(self, new_state: PLCConnectionState) -> None:
        """Cập nhật trạng thái và gọi callback"""
        if self._state != new_state:
            self._state = new_state
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except:
                    pass
    
    def _report_error(self, message: str) -> None:
        """Báo lỗi qua callback"""
        if self.on_error:
            try:
                self.on_error(message)
            except:
                pass
    
    def set_enabled(self, enabled: bool) -> None:
        """Bật/tắt PLC client"""
        self._enabled = enabled
        if not enabled:
            self.disconnect()
    
    def reset_reconnect_counter(self) -> None:
        """Reset counter reconnect"""
        self._reconnect_count = 0

