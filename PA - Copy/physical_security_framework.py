#!/usr/bin/env python3


import os
import sys
import time
from typing import List, Tuple, Optional, Dict, Any

# try-except blocks for optional dependencies
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("[!] OpenCV not available - some modules will be disabled")

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[!] requests/BeautifulSoup not available - social engineering module limited")

try:
    from smtplib import SMTP
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    SMTP_AVAILABLE = True
except ImportError:
    SMTP_AVAILABLE = False
    print("[!] smtplib not available - impersonation module limited")

try:
    from rtlsdr import RtlSdr
    RTLSDR_AVAILABLE = True
except ImportError:
    RTLSDR_AVAILABLE = False
    print("[!] pyrtlsdr not available - RF analysis module limited")

try:
    import serial
    SERIAL_AVAILABLE = True
    import serial.tools.list_ports
except ImportError:
    SERIAL_AVAILABLE = False
    print("[!] pyserial not available - hardware interface modules limited")


# ============================================================================
# Base Module Classes and Utilities
# ============================================================================

class ModuleBase:
    """Base class for all bypass modules."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.name = self.__class__.__name__

    def log(self, message: str, level: str = "INFO"):
        """Standardized logging for all modules."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] [{self.name}] {message}")

    def log_success(self, message: str):
        self.log(message, "SUCCESS")

    def log_error(self, message: str):
        self.log(message, "ERROR")

    def log_warning(self, message: str):
        self.log(message, "WARNING")


class HardwareModule(ModuleBase):
    """Base class for modules requiring hardware interaction."""

    def __init__(self, device: Optional[str] = None, verbose: bool = False):
        super().__init__(verbose)
        self.device = device
        self.connection = None

    def connect(self) -> bool:
        """Establish connection to hardware device."""
        raise NotImplementedError

    def disconnect(self):
        """Close connection to hardware device."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.log_success("Disconnected from hardware")


# ============================================================================
# Module 1: Tailgating/Piggybacking Module (Thermal Camera Analysis)
# ============================================================================

class TailgatingModule(ModuleBase):
    """Thermal Camera Analysis Module for PIN Pad Heat Signature Detection"""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        if not OPENCV_AVAILABLE:
            raise RuntimeError("OpenCV is required for thermal analysis")

    def detect_heat_signatures(self, image_path: str, output_dir: str = None) -> Dict[str, Any]:
        """Analyze thermal image for heat signatures on PIN pad."""
        if not OPENCV_AVAILABLE:
            self.log_error("OpenCV not available")
            return {}

        self.log(f"Analyzing thermal image: {image_path}")

        img = cv2.imread(image_path)
        if img is None:
            self.log_error(f"Failed to load image: {image_path}")
            return {}

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_size, max_size = 50, 500
        hotspots = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if min_size < area < max_size:
                x, y, w, h = cv2.boundingRect(cnt)
                hotspots.append({'position': (x, y), 'size': area, 'confidence': min(1.0, area / max_size)})

        hotspots.sort(key=lambda h: (h['position'][1], h['position'][0]))
        key_mapping = self._map_to_keypad(hotspots)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            cv2.imwrite(os.path.join(output_dir, "analysis_result.jpg"), img)
            self.log_success(f"Analysis saved to: {output_dir}/analysis_result.jpg")

        return {'detected_keys': key_mapping, 'hotspots': hotspots, 'total_signatures': len(hotspots)}

    def _map_to_keypad(self, hotspots: List[Dict]) -> List[Dict]:
        if not hotspots:
            return []
        keys = []
        keypad_map = [
            ['1', '2', '3', '*'], ['4', '5', '6', 'B'],
            ['7', '8', '9', 'C'], ['*', '0', '#', 'D']
        ]
        for i, hotspot in enumerate(hotspots[:12]):
            row, col = i // 4, i % 4
            if row < len(keypad_map) and col < len(keypad_map[row]):
                keys.append({'key': keypad_map[row][col], 'position': hotspot['position'], 'confidence': hotspot['confidence']})
        return keys

    def analyze_pin_pattern(self, detected_keys: List[Dict]) -> str:
        """Analyze detected key pattern to extract likely PIN."""
        if not detected_keys:
            return ""
        pin_digits = [str(k.get('key', '')) for k in sorted(detected_keys, key=lambda x: x.get('confidence', 0), reverse=True) if str(k.get('key', '')).isdigit()]
        seen = set()
        unique_digits = [d for d in pin_digits if d not in seen and not seen.add(d)]
        return ''.join(unique_digits[:6])


# ============================================================================
# Module 2: Badge Cloning Module (Proxmark3 Interface)
# ============================================================================

class BadgeCloningModule(HardwareModule):
    """RFID/NFC Badge Cloning Module using Proxmark3"""

    DEFAULT_BAUDRATE = 115200
    DEFAULT_TIMEOUT = 5.0

    def __init__(self, verbose: bool = False):
        super().__init__(None, verbose)
        self.device = self._find_proxmark3_device()

    def _find_proxmark3_device(self) -> Optional[str]:
        if not SERIAL_AVAILABLE:
            return None
        for port in serial.tools.list_ports.comports():
            if any(identifier in port.description.lower() for identifier in ['proxmark3', 'pm3', 'acm', 'usb serial']):
                self.log(f"Auto-detected Proxmark3 on {port.device}")
                return port.device
        self.log_warning("No Proxmark3 device auto-detected")
        return None

    def connect(self) -> bool:
        if not SERIAL_AVAILABLE or not self.device:
            self.log_error("pyserial or device not available")
            return False
        try:
            self.connection = serial.Serial(self.device, self.DEFAULT_BAUDRATE, timeout=self.DEFAULT_TIMEOUT)
            time.sleep(2)
            self._send_command("hw status")
            response = self._read_response()
            if "OK" in response or "pm3" in response.lower():
                self.log_success(f"Connected to Proxmark3 on {self.device}")
                return True
            self.log_error("Failed to connect to Proxmark3")
            self.disconnect()
            return False
        except Exception as e:
            self.log_error(f"Connection failed: {e}")
            return False

    def _send_command(self, command: str):
        if self.connection:
            self.connection.write(f"{command}\r\n".encode())
            time.sleep(0.1)

    def _read_response(self, timeout: float = 2.0) -> str:
        if not self.connection:
            return ""
        self.connection.timeout = timeout
        return self.connection.read(4096).decode('utf-8', errors='ignore')

    def read_uid(self, card_type: str = "any") -> Optional[str]:
        """Read UID from RFID/NFC card."""
        self.log(f"Attempting to read card UID (type: {card_type})")
        commands = {"any": "hid read", "iso14443a": "iso14443a read", "iso14443b": "iso14443b read", "mifare": "mifare rdd1"}
        self._send_command(commands.get(card_type, "hid read"))
        time.sleep(1)
        response = self._read_response(timeout=10)
        import re
        uid_match = re.search(r'[0-9A-Fa-f]{8,20}', response)
        if uid_match:
            uid = uid_match.group()
            self.log_success(f"Card UID detected: {uid}")
            return uid
        self.log_warning("No UID detected")
        return None

    def clone_card(self, source_uid: str, target_device: str = "em4x") -> bool:
        """Clone card by writing to blank tag."""
        self.log(f"Attempting to clone UID: {source_uid}")
        self._send_command(f"sim {target_device} {source_uid}")
        self._send_command("lf sim")
        self._send_command("hf sim")
        self.log_success("Clone simulation complete")
        return True


# ============================================================================
# Module 3: Lock Picking Module (Decoder Calculator)
# ============================================================================

class LockPickingModule(ModuleBase):
    """Pin Tumbler Lock Decoder Calculator"""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        self.specs = {
            'common': {'pin_count': 5, 'driver_pin_height': 0.100, 'key_pin_height_unit': 0.005, 'total_depth_range': 0.300},
            'medeco': {'pin_count': 6, 'driver_pin_height': 0.115, 'key_pin_height_unit': 0.005, 'total_depth_range': 0.350},
            'schlage': {'pin_count': 5, 'driver_pin_height': 0.100, 'key_pin_height_unit': 0.004, 'total_depth_range': 0.320}
        }

    def calculate_bitting(self, decoder_readings: List[float], lock_type: str = 'common') -> Dict[str, Any]:
        """Calculate key bitting from decoder readings."""
        s = self.specs.get(lock_type, self.specs['common'])
        bitting = [max(1, min(int(r / s['key_pin_height_unit']), int(s['total_depth_range'] / s['key_pin_height_unit']))) for r in decoder_readings]
        key_diagram = ['█' * int(d / max(bitting) * 20) + '░' * (20 - int(d / max(bitting) * 20)) for d in bitting]
        return {
            'lock_type': lock_type, 'pin_count': s['pin_count'],
            'bitting_code': ''.join(map(str, bitting)), 'bitting_list': bitting,
            'key_depths': {'diagram': key_diagram}
        }


# ============================================================================
# Module 4: Social Engineering Module (OSINT Scraper)
# ============================================================================

class SocialEngineeringModule(ModuleBase):
    """OSINT Information Gathering Module"""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests and BeautifulSoup required")
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    def scrape_company_website(self, domain: str) -> List[Dict]:
        """Scrape employee information from company website."""
        self.log(f"Scraping domain: {domain}")
        paths = ['/about', '/leadership', '/team', '/contact', '/people', '/careers']
        profiles = []
        for path in paths:
            try:
                response = self.session.get(f"https://{domain}{path}", timeout=10)
                if response.status_code == 200:
                    self.log(f"Found page: {path}")
                    soup = BeautifulSoup(response.text, 'html.parser')
                    for elem in soup.find_all(['h2', 'h3', 'div', 'a']):
                        name = elem.get_text(strip=True)
                        if name and len(name.split()) <= 4:
                            profiles.append({'name': name, 'source': path, 'role': 'unknown'})
            except Exception as e:
                self.log_warning(f"Failed to fetch {path}: {e}")
        # Deduplicate
        seen = set()
        unique = []
        for p in profiles:
            k = p['name'].lower().strip()
            if k not in seen:
                seen.add(k)
                unique.append(p)
        return unique


# ============================================================================
# Module 5: Dumpster Diving Module (Shredded Document Reconstruction)
# ============================================================================

class DumpsterDivingModule(ModuleBase):
    """Shredded Document Reconstruction Module"""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        if not OPENCV_AVAILABLE:
            raise RuntimeError("OpenCV required")

    def detect_shredded_edges(self, image_path: str) -> List[Dict]:
        """Detect edges of shredded document pieces."""
        self.log(f"Processing image: {image_path}")
        img = cv2.imread(image_path)
        if img is None:
            self.log_error(f"Failed to load image: {image_path}")
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        pieces = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 1000 < area < edges.shape[0] * edges.shape[1] / 4:
                x, y, w, h = cv2.boundingRect(cnt)
                pieces.append({'area': area, 'bounding_box': (x, y, w, h), 'aspect_ratio': w / h if h > 0 else 0})
        return pieces


# ============================================================================
# Module 6: USB Drop Attack Module (DuckyScript Generator)
# ============================================================================

class USBDropAttackModule(ModuleBase):
    """DuckyScript Payload Generator for Rubber Ducky / BadUSB"""

    def generate_ducky_script(self, commands: List[str]) -> str:
        """Generate DuckyScript from commands."""
        script_lines = ["DELAY 1000", "DELAY 1000", ""]
        for cmd in commands:
            c = cmd.split('#')[0].strip().lower()
            if c == 'delay':
                script_lines.append("DELAY 1000")
            elif c == 'wait':
                script_lines.append("DELAY 2000")
            elif c == 'enter':
                script_lines.append("ENTER")
            else:
                import re
                strings = re.findall(r'"([^"]*)"', cmd)
                converted = cmd
                for s in strings:
                    converted = converted.replace(f'"{s}"', f'STRING {s}')
                script_lines.append(converted)
        script_lines.extend(["", "DELAY 500", "ENTER", ""])
        return '\n'.join(script_lines)

    def create_rubber_ducky_payload(self, target_os: str = 'windows', command: str = 'calc.exe') -> str:
        """Create pre-configured Rubber Ducky payload."""
        if target_os == 'windows':
            return '\n'.join(["DELAY 1000", "GUI r", "DELAY 500", f"STRING {command}", "DELAY 500", "ENTER", "DELAY 1000", "ENTER"])
        elif target_os == 'linux':
            return '\n'.join(["DELAY 1000", "ALT F2", "DELAY 500", f"STRING x-terminal-emulator -e bash -c '{command}'", "ENTER", "DELAY 500", "ENTER"])
        elif target_os == 'mac':
            return '\n'.join(["DELAY 1000", "GUI SPACE", "DELAY 500", "STRING terminal", "ENTER", "DELAY 500", f"STRING {command}", "ENTER"])
        raise ValueError(f"Unsupported OS: {target_os}")


# ============================================================================
# Module 7: RF Signal Analysis Module
# ============================================================================

class RFSignalAnalysisModule(HardwareModule):
    """RF Signal Analysis Module using RTL-SDR"""

    def __init__(self, frequency: float = 433.92e6, sample_rate: float = 2.4e6, gain: int = 20, verbose: bool = False):
        super().__init__(None, verbose)
        if not RTLSDR_AVAILABLE:
            raise RuntimeError("pyrtlsdr required")
        self.frequency = frequency
        self.sample_rate = sample_rate
        self.gain = gain
        self.sdr = None

    def connect(self) -> bool:
        try:
            self.sdr = RtlSdr(device_index=0)
            self.sdr.sample_rate = self.sample_rate
            self.sdr.center_freq = self.frequency
            self.sdr.gain = self.gain
            self.log_success(f"RTL-SDR connected: F={self.frequency/1e6:.2f}MHz")
            return True
        except Exception as e:
            self.log_error(f"RTL-SDR connection failed: {e}")
            return False

    def tune_frequency(self, frequency: float) -> bool:
        if not self.sdr:
            self.log_error("SDR not connected")
            return False
        self.sdr.center_freq = frequency
        self.frequency = frequency
        self.log(f"Tuned to {frequency/1e6:.2f} MHz")
        return True

    def capture_signal(self, duration: float = 1.0) -> Optional[np.ndarray]:
        """Capture RF signal data."""
        if not self.sdr:
            self.log_error("SDR not connected")
            return None
        num_samples = int(self.sample_rate * duration)
        self.log(f"Capturing {duration}s of RF data...")
        samples = []
        batch_size = 1024
        for i in range(0, num_samples, batch_size):
            read_samples = self.sdr.read_samples(min(batch_size, num_samples - i))
            samples.extend(read_samples)
            if len(samples) % (batch_size * 10) == 0:
                self.log(f"Captured: {len(samples)}/{num_samples}")
        samples = np.array(samples, dtype=np.complex64)
        self.log_success(f"Captured {len(samples)} samples")
        return samples

    def analyze_signal(self, samples: np.ndarray) -> Dict[str, Any]:
        """Analyze captured RF signal."""
        if len(samples) < 100:
            return {}
        amplitude = np.abs(samples)
        mean_amp = np.mean(amplitude)
        std_amp = np.std(amplitude)
        snr = 10 * np.log10((mean_amp ** 2) / (std_amp ** 2)) if std_amp > 0 else float('inf')
        phase_diff = np.diff(np.unwrap(np.angle(samples)))
        if np.std(amplitude) > mean_amp * 0.5 and np.std(phase_diff) < 0.1:
            modulation = "AM"
        elif np.std(phase_diff) > 0.5:
            modulation = "FM"
        elif mean_amp > 0.5 and std_amp < 0.3:
            modulation = "OOK/ASK"
        else:
            modulation = "Unknown"
        return {'mean_amplitude': float(mean_amp), 'std_amplitude': float(std_amp), 'snr_db': float(snr), 'modulation_type': modulation}


# ============================================================================
# Module 8: CCTV Blind Spot Exploitation Module
# ============================================================================

class CCTVBlindSpotModule(ModuleBase):
    """CCTV Blind Spot Analysis Module"""

    def calculate_blind_spots(self, room_dimensions: Dict[str, float], camera_positions: List[Dict]) -> Dict[str, Any]:
        """Calculate blind spots in a room."""
        self.log("Calculating CCTV blind spots...")
        length, width, height = room_dimensions['length'], room_dimensions['width'], room_dimensions['height']
        blind_spots = []
        coverage_map = np.zeros((int(width * 10), int(length * 10)))

        for i, camera in enumerate(camera_positions):
            self.log(f"Analyzing Camera {i+1}: ({camera['x']}, {camera['y']}) @ {camera['angle']}°")
            fov = camera.get('fov', 90)
            angle = camera['angle']
            camera_x, camera_y = camera['x'] * 10, camera['y'] * 10

            # Calculate coverage
            start_angle, end_angle = angle - fov / 2, angle + fov / 2
            for j in range(100):
                ray_angle = start_angle + (end_angle - start_angle) * j / 100
                rad = np.radians(ray_angle)
                dx, dy = np.cos(rad), np.sin(rad)
                ray_x, ray_y = camera_x, camera_y
                step = 1
                while 0 <= ray_x <= length * 10 and 0 <= ray_y <= width * 10:
                    if 0 <= int(ray_y) < coverage_map.shape[0] and 0 <= int(ray_x) < coverage_map.shape[1]:
                        coverage_map[int(ray_y), int(ray_x)] += 1
                    ray_x += dx * step
                    ray_y += dy * step

            # Find blind spots
            corner_areas = [{'x': 0, 'y': 0}, {'x': length, 'y': 0}, {'x': 0, 'y': width}, {'x': length, 'y': width}]
            for corner in corner_areas:
                if not self._is_corner_visible(camera, corner, length, width):
                    blind_spots.append({'type': 'corner', 'x': corner['x'], 'y': corner['y'], 'reason': f"Camera {i+1} cannot see corner"})

        uncovered = np.argwhere(coverage_map == 0)
        total_area = length * width
        blind_spot_area = len(uncovered) / coverage_map.size * total_area

        recommendations = []
        if blind_spots:
            recommendations.append(f"Add {len(blind_spots)} additional camera(s) to cover blind spots")
            recommendations.append("Consider installing corner mirrors")
        if len(camera_positions) < 3:
            recommendations.append("Minimum 3 cameras recommended for comprehensive coverage")

        return {
            'room_dimensions': room_dimensions, 'camera_count': len(camera_positions),
            'blind_spots': blind_spots, 'uncovered_regions': len(uncovered),
            'blind_spot_percentage': blind_spot_area / total_area * 100,
            'recommendations': recommendations
        }

    def _is_corner_visible(self, camera: Dict, corner: Dict, length: float, width: float) -> bool:
        """Check if corner is visible from camera position."""
        dx, dy = corner['x'] - camera['x'], corner['y'] - camera['y']
        angle_to_corner = np.degrees(np.atan2(dy, dx))
        camera_angle = camera['angle'] % 360
        angle_diff = abs(angle_to_corner - camera_angle)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff
        fov = camera.get('fov', 90)
        if angle_diff < fov / 2:
            return True
        if camera['x'] < 0.5 and corner['x'] > length - 0.5:
            return False
        if camera['x'] > length - 0.5 and corner['x'] < 0.5:
            return False
        if camera['y'] < 0.5 and corner['y'] > width - 0.5:
            return False
        if camera['y'] > width - 0.5 and corner['y'] < 0.5:
            return False
        return True


# ============================================================================
# Module 9: Impersonation Module (Email Spoofing)
# ============================================================================

class ImpersonationModule(ModuleBase):
    """Email Spoofing Module for Impersonation Testing"""

    def __init__(self, verbose: bool = False):
        super().__init__(verbose)
        if not SMTP_AVAILABLE:
            raise RuntimeError("smtplib required")

    def spoof_email(self, sender_name: str, sender_email: str, recipient: str, subject: str, body: str,
                   smtp_server: str = 'localhost', smtp_port: int = 25) -> bool:
        """Send a spoofed email."""
        self.log(f"Preparing spoofed email from: {sender_name} <{sender_email}>")
        try:
            msg = MIMEMultipart()
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = recipient
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))

            server = SMTP(smtp_server, smtp_port)
            server.sendmail(sender_email, [recipient], msg.as_string())
            server.quit()
            self.log_success("Email sent successfully")
            return True
        except Exception as e:
            self.log_error(f"Error sending email: {e}")
            return False

    def generate_phishing_template(self, target_name: str, target_role: str, company_name: str) -> Dict[str, str]:
        """Generate a phishing email template."""
        return {
            'subject': f"Urgent: Physical Access Authorization - {target_role}",
            'from_name': "Executive Management",
            'from_email': f"ceo@{company_name.lower()}.com",
            'body': f"<html><body><p>Dear {target_name},<p><p>I'm authorizing physical access for a critical contractor.</p><p>Please approve the following contractor for immediate access:</p><ul><li><strong>Name:</strong> IT Support Contractor</li><li><strong>ID:</strong> TEMP-2024-001</li></ul></body></html>"
        }


# ============================================================================
# Module 10: Door Frame Manipulation Module (Arduino Interface)
# ============================================================================

class DoorFrameManipulationModule(HardwareModule):
    """Arduino-Based Door Manipulation Module"""

    BAUD_RATE = 9600
    TIMEOUT = 3.0

    def __init__(self, verbose: bool = False):
        super().__init__(None, verbose)
        self.device = self._find_arduino_device()

    def _find_arduino_device(self) -> Optional[str]:
        if not SERIAL_AVAILABLE:
            return None
        for port in serial.tools.list_ports.comports():
            if any(identifier in port.description.lower() for identifier in ['arduino', 'usb serial', 'cp2102', 'ch340']):
                self.log(f"Auto-detected Arduino on {port.device}")
                return port.device
        self.log_warning("No Arduino device auto-detected")
        return None

    def connect(self) -> bool:
        if not SERIAL_AVAILABLE or not self.device:
            self.log_error("pyserial or device not available")
            return False
        try:
            self.connection = serial.Serial(self.device, self.BAUD_RATE, timeout=self.TIMEOUT)
            time.sleep(2)
            self.log_success(f"Connected to Arduino on {self.device}")
            return True
        except Exception as e:
            self.log_error(f"Connection failed: {e}")
            return False

    def send_command(self, command: str) -> bool:
        if not self.connection:
            self.log_error("Not connected to Arduino")
            return False
        try:
            self.connection.write(f"{command}\n".encode())
            time.sleep(0.1)
            return True
        except Exception as e:
            self.log_error(f"Failed to send command: {e}")
            return False

    def read_response(self) -> str:
        if not self.connection:
            return ""
        try:
            return self.connection.readline().decode('utf-8', errors='ignore').strip()
        except Exception:
            return ""

    def open_door(self) -> bool:
        self.log("Attempting to open door...")
        if self.send_command('O'):
            response = self.read_response()
            self.log_success(f"Door open command sent: {response}")
            return True
        return False

    def close_door(self) -> bool:
        self.log("Attempting to close door...")
        if self.send_command('C'):
            response = self.read_response()
            self.log_success(f"Door close command sent: {response}")
            return True
        return False

    def check_lock_status(self) -> str:
        if self.send_command('L'):
            return self.read_response() or "Unknown"
        return "Error"

    def bypass_latch(self) -> bool:
        self.log("Attempting latch bypass...")
        if self.send_command('B'):
            response = self.read_response()
            self.log_success(f"Latch bypass: {response}")
            return True
        return False


# ============================================================================
# Main Framework - Interactive CLI
# ============================================================================

class PhysicalSecurityFramework:
    """Central Command-Line Interface for the Physical Security Bypass Framework."""

    def __init__(self):
        self.modules = {}
        self.verbose = False
        self._init_modules()

    def _init_modules(self):
        """Initialize all available modules."""
        # Always available
        self.modules['lockpicking'] = LockPickingModule()
        self.modules['usb'] = USBDropAttackModule()
        self.modules['cctv'] = CCTVBlindSpotModule()

        # Conditionally available
        if OPENCV_AVAILABLE:
            self.modules['tailgating'] = TailgatingModule()
            self.modules['dumpster'] = DumpsterDivingModule()
        else:
            self.modules['tailgating'] = None
            self.modules['dumpster'] = None

        if REQUESTS_AVAILABLE:
            self.modules['social'] = SocialEngineeringModule()
        else:
            self.modules['social'] = None

        if RTLSDR_AVAILABLE:
            self.modules['rf'] = RFSignalAnalysisModule()
        else:
            self.modules['rf'] = None

        if SMTP_AVAILABLE:
            self.modules['impersonate'] = ImpersonationModule()
        else:
            self.modules['impersonate'] = None

        if SERIAL_AVAILABLE:
            self.modules['badge'] = BadgeCloningModule()
            self.modules['door'] = DoorFrameManipulationModule()
        else:
            self.modules['badge'] = None
            self.modules['door'] = None

    def print_banner(self):
        """Print framework banner."""
        print("=" * 60)
        print("  PHYSICAL SECURITY BYPASS FRAMEWORK v1.0.0")
        print("  Authorized Penetration Testing Tool")
        print("=" * 60)
        print("  WARNING: For authorized security testing only.")
        print("  Unauthorized access to physical systems is illegal.")
        print("=" * 60)

    def print_modules(self):
        """Print available modules."""
        print("\nAvailable Modules:")
        print("-" * 60)
        for name, module in self.modules.items():
            status = "ENABLED" if module else "DISABLED (missing dependencies)"
            print(f"  [{name:15}] {status}")

    def menu(self):
        """Display interactive menu and handle selection."""
        while True:
            self.print_banner()
            self.print_modules()

            print("\n" + "=" * 60)
            print("SELECT MODULE TO RUN")
            print("=" * 60)
            for i, (name, module) in enumerate(self.modules.items(), 1):
                status = "ENABLED" if module else "DISABLED"
                print(f"  {i:2}. {name:15} [{status}]")

            print("  0. Exit")
            print("-" * 60)

            try:
                choice = input("\nEnter your choice (0-10): ").strip()
                if choice == '0':
                    print("Exiting...")
                    break

                choice_num = int(choice)
                module_names = list(self.modules.keys())
                if 1 <= choice_num <= len(module_names):
                    module_name = module_names[choice_num - 1]
                    self._run_module(module_name)
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Invalid input. Please enter a number.")
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                break

    def _run_module(self, module_name: str):
        """Run selected module."""
        module = self.modules[module_name]
        if not module:
            print(f"[ERROR] Module '{module_name}' is not available (missing dependencies)")
            input("\nPress Enter to continue...")
            return

        print(f"\n{'=' * 60}")
        print(f"RUNNING MODULE: {module_name.upper()}")
        print('=' * 60)

        try:
            if module_name == 'tailgating':
                self._run_tailgating(module)
            elif module_name == 'badge':
                self._run_badge(module)
            elif module_name == 'lockpicking':
                self._run_lockpicking(module)
            elif module_name == 'social':
                self._run_social(module)
            elif module_name == 'dumpster':
                self._run_dumpster(module)
            elif module_name == 'usb':
                self._run_usb(module)
            elif module_name == 'rf':
                self._run_rf(module)
            elif module_name == 'cctv':
                self._run_cctv(module)
            elif module_name == 'impersonate':
                self._run_impersonate(module)
            elif module_name == 'door':
                self._run_door(module)
        except Exception as e:
            print(f"[ERROR] {e}")
        finally:
            input("\nPress Enter to return to menu...")

    def _run_tailgating(self, module: TailgatingModule):
        """Run tailgating module."""
        image_path = input("Enter path to thermal image: ").strip()
        output_dir = input("Enter output directory (optional, press Enter to skip): ").strip() or None
        result = module.detect_heat_signatures(image_path, output_dir)
        if result.get('detected_keys'):
            print("\nDetected Keys:")
            for key_info in result['detected_keys']:
                print(f"  Key: {key_info['key']} | Position: {key_info['position']} | Confidence: {key_info['confidence']:.2f}")
        else:
            print("No heat signatures detected.")

    def _run_badge(self, module: BadgeCloningModule):
        """Run badge cloning module."""
        if not module.connect():
            print("[ERROR] Failed to connect to Proxmark3")
            return
        try:
            uid = module.read_uid()
            if uid:
                print(f"\n[SUCCESS] Card UID: {uid}")
                clone = input("Clone this card? (y/n): ").strip().lower()
                if clone == 'y':
                    module.clone_card(uid)
        finally:
            module.disconnect()

    def _run_lockpicking(self, module: LockPickingModule):
        """Run lockpicking module."""
        print("Enter decoder readings (in 0.005\" increments, separated by spaces):")
        readings_str = input("> ").strip()
        readings = [float(r) for r in readings_str.split()]
        print("\nSelect lock type:")
        print("  1. Common (standard pins)")
        print("  2. Medeco (6 pins)")
        print("  3. Schlage (standard)")
        lock_choice = input("> ").strip()
        lock_types = {'1': 'common', '2': 'medeco', '3': 'schlage'}
        lock_type = lock_types.get(lock_choice, 'common')
        result = module.calculate_bitting(readings, lock_type)
        print(f"\nLock Type: {result['lock_type']}")
        print(f"Pin Count: {result['pin_count']}")
        print(f"Bitting Code: {result['bitting_code']}")
        print("\nKey Depth Diagram:")
        for i, depth in enumerate(result['key_depths']['diagram'], 1):
            print(f"  Pin {i}: {depth}")

    def _run_social(self, module: SocialEngineeringModule):
        """Run social engineering module."""
        domain = input("Enter target domain (e.g., example.com): ").strip()
        profiles = module.scrape_company_website(domain)
        print(f"\nCollected {len(profiles)} profiles:")
        for profile in profiles[:20]:
            print(f"  - {profile.get('name', 'Unknown')}")

    def _run_dumpster(self, module: DumpsterDivingModule):
        """Run dumpster diving module."""
        image_path = input("Enter path to shredded document image: ").strip()
        pieces = module.detect_shredded_edges(image_path)
        print(f"\nDetected {len(pieces)} document pieces:")
        for i, piece in enumerate(pieces[:10], 1):
            print(f"  Piece {i}: Area={piece['area']:.0f}, Aspect Ratio={piece['aspect_ratio']:.2f}")

    def _run_usb(self, module: USBDropAttackModule):
        """Run USB drop attack module."""
        print("\nSelect payload type:")
        print("  1. DuckyScript from custom commands")
        print("  2. Pre-configured payload (Windows)")
        print("  3. Pre-configured payload (Linux)")
        print("  4. Pre-configured payload (Mac)")
        choice = input("> ").strip()
        if choice == '1':
            print("Enter commands (one per line, press Ctrl+D when done):")
            commands = []
            try:
                while True:
                    cmd = input("  > ").strip()
                    if cmd:
                        commands.append(cmd)
            except EOFError:
                pass
            script = module.generate_ducky_script(commands)
        elif choice == '2':
            command = input("Enter Windows command (e.g., calc.exe): ").strip()
            script = module.create_rubber_ducky_payload('windows', command)
        elif choice == '3':
            command = input("Enter Linux command: ").strip()
            script = module.create_rubber_ducky_payload('linux', command)
        elif choice == '4':
            command = input("Enter Mac command: ").strip()
            script = module.create_rubber_ducky_payload('mac', command)
        else:
            print("Invalid choice.")
            return
        print("\n" + "=" * 40)
        print("GENERATED DUCKYSCRIPT:")
        print("=" * 40)
        print(script)
        save = input("\nSave to file? (y/n): ").strip().lower()
        if save == 'y':
            filename = input("Enter filename: ").strip()
            with open(filename, 'w') as f:
                f.write(script)
            print(f"Saved to {filename}")

    def _run_rf(self, module: RFSignalAnalysisModule):
        """Run RF analysis module."""
        if not module.connect():
            print("[ERROR] Failed to connect to RTL-SDR")
            return
        try:
            freq = input(f"Enter frequency in MHz (default {module.frequency/1e6:.2f}): ").strip()
            if freq:
                module.tune_frequency(float(freq) * 1e6)
            duration = input("Enter capture duration in seconds (default 1.0): ").strip()
            duration = float(duration) if duration else 1.0
            samples = module.capture_signal(duration)
            if samples is not None:
                analysis = module.analyze_signal(samples)
                print("\nRF Analysis Results:")
                print(f"  Mean Amplitude: {analysis.get('mean_amplitude', 0):.3f}")
                print(f"  SNR: {analysis.get('snr_db', 0):.1f} dB")
                print(f"  Modulation: {analysis.get('modulation_type', 'Unknown')}")
        finally:
            module.disconnect()

    def _run_cctv(self, module: CCTVBlindSpotModule):
        """Run CCTV blind spot analysis."""
        print("Enter room dimensions:")
        length = float(input("  Length (m): ").strip() or 10)
        width = float(input("  Width (m): ").strip() or 8)
        height = float(input("  Height (m): ").strip() or 2.5)
        room = {'length': length, 'width': width, 'height': height}

        cameras = []
        num_cameras = int(input("\nHow many cameras? ").strip() or 1)
        for i in range(num_cameras):
            print(f"Camera {i+1} position:")
            cam_x = float(input(f"  X (m, default 5): ").strip() or 5)
            cam_y = float(input(f"  Y (m, default 5): ").strip() or 5)
            cam_angle = float(input(f"  Angle (degrees, default 0): ").strip() or 0)
            cam_fov = float(input(f"  FOV (degrees, default 90): ").strip() or 90)
            cameras.append({'x': cam_x, 'y': cam_y, 'angle': cam_angle, 'fov': cam_fov})

        result = module.calculate_blind_spots(room, cameras)
        print(f"\nCCTV Analysis Results:")
        print(f"  Room: {length}m x {width}m x {height}m")
        print(f"  Cameras: {result['camera_count']}")
        print(f"  Blind Spot Percentage: {result['blind_spot_percentage']:.1f}%")
        print(f"  Blind Spots: {len(result['blind_spots'])}")
        if result['recommendations']:
            print("\nRecommendations:")
            for rec in result['recommendations'][:5]:
                print(f"  * {rec}")

    def _run_impersonate(self, module: ImpersonationModule):
        """Run email impersonation module."""
        print("Enter email details:")
        sender_name = input("  Sender Name: ").strip() or "Executive"
        sender_email = input("  Sender Email: ").strip() or "ceo@company.com"
        recipient = input("  Recipient Email: ").strip()
        subject = input("  Subject: ").strip() or "Urgent: Physical Access Authorization"
        body = input("  Body: ").strip() or "Please approve contractor access."
        smtp_server = input("  SMTP Server (default localhost): ").strip() or "localhost"
        smtp_port = int(input("  SMTP Port (default 25): ").strip() or 25)

        success = module.spoof_email(sender_name, sender_email, recipient, subject, body, smtp_server, smtp_port)
        if success:
            print(f"\n[SUCCESS] Email sent to {recipient}")
        else:
            print("\n[FAILED] Could not send email")

    def _run_door(self, module: DoorFrameManipulationModule):
        """Run door manipulation module."""
        if not module.connect():
            print("[ERROR] Failed to connect to Arduino")
            return
        try:
            print("\nDoor Commands:")
            print("  O - Open door")
            print("  C - Close door")
            print("  L - Check lock status")
            print("  B - Bypass latch")
            print("  S - Stop action")
            command = input("\nEnter command: ").strip().upper()
            if command == 'O':
                module.open_door()
            elif command == 'C':
                module.close_door()
            elif command == 'L':
                status = module.check_lock_status()
                print(f"Lock Status: {status}")
            elif command == 'B':
                module.bypass_latch()
            elif command == 'S':
                module.stop_action()
            else:
                print("Invalid command.")
        finally:
            module.disconnect()


def main():
    """Main entry point."""
    framework = PhysicalSecurityFramework()
    framework.menu()


if __name__ == '__main__':
    main()
