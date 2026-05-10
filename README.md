# Physical Security Bypass Framework

## Table of Contents
- [Features and Modules](#features-and-modules)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Hardware Setup Notes](#hardware-setup-notes)
- [Contributing](#contributing)

---

## Features and Modules

The framework is divided into 10 independent modules. The core engine will automatically detect available software dependencies and connected hardware, enabling or disabling modules dynamically.

1. **Tailgating (Thermal Camera Analysis):** Utilizes OpenCV to isolate and map residual heat signatures on electronic PIN pads to deduce recently pressed keys.
2. **Badge Cloning (Proxmark3 Wrapper):** An automated serial interface for the Proxmark3 to read, capture, and clone low/high-frequency RFID and NFC badges.
3. **Lock Picking (Decoder Calculator):** A mathematical calculator that translates analog decoder pick measurements into exact bitting codes for key replication.
4. **Social Engineering (OSINT Scraper):** Automates the scraping of corporate directories using `requests` and `BeautifulSoup` to map out target profiles.
5. **Dumpster Diving (Document Reconstruction):** Employs OpenCV edge-detection algorithms to computationally analyze and align scanned pieces of shredded documents.
6. **USB Drop Attack (Payload Generator):** A compiler module that translates plain-text intent into functional DuckyScript payloads for USB Rubber Ducky and BadUSB devices.
7. **RF Signal Analysis (RTL-SDR):** Interfaces with an RTL-SDR dongle to capture and analyze sub-GHz radio frequencies used in keyless entry and alarm systems.
8. **CCTV Exploitation (Blind Spot Mapper):** A 2D ray-casting simulator that calculates optical blind spots based on room dimensions and camera field-of-view (FOV).
9. **Impersonation (Email Spoofing):** Forges SMTP headers to craft convincing phishing emails (e.g., authorizing physical entry for a contractor).
10. **Door Frame Manipulation (Arduino Actuator):** A serial communication module designed to send byte-sized trigger commands to custom Arduino-based mechanical bypass tools.

---

## Prerequisites

### Software Dependencies
The framework requires Python 3.6 or higher. The following libraries are required to enable all software-based modules:
* `opencv-python` (Module 1, 5)
* `numpy` (Module 7, 8)
* `requests` & `beautifulsoup4` (Module 4)
* `pyrtlsdr` (Module 7)
* `pyserial` (Module 2, 10)

### Supported Hardware
To fully utilize the hardware-interaction modules, the following equipment is recommended:
* **Proxmark3** (Connected via USB)
* **RTL-SDR Dongle** (e.g., RTL2832U with appropriate OS drivers)
* **Arduino Microcontroller** (Flashed with custom bypass sketch)
* **Hak5 USB Rubber Ducky** (For payload deployment)

Set up a virtual environment (Optional but recommended):

Bash
python3 -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
Install the dependencies:

Bash
pip install opencv-python numpy requests beautifulsoup4 pyrtlsdr pyserial

python3 physical_security_framework.py

Author 
Varad Gandhi
