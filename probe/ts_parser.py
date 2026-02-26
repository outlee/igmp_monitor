import struct
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TSPacket:
    pid: int
    cc: int
    payload_unit_start: bool
    has_payload: bool
    has_adaptation: bool
    payload: bytes
    adaptation: bytes
    pcr: Optional[int] = None
    transport_error: bool = False


@dataclass
class StreamInfo:
    stream_type: int
    pid: int


@dataclass
class TSParserState:
    channel_id: str
    pat: Dict[int, int] = field(default_factory=dict)
    pmt_pids: Set[int] = field(default_factory=set)
    video_pid: int = -1
    audio_pid: int = -1
    pcr_pid: int = -1
    service_name: str = ""
    event_name: str = ""
    pid_cc: Dict[int, int] = field(default_factory=dict)
    cc_errors: int = 0
    last_pcr: Optional[int] = None
    last_pcr_time: Optional[float] = None
    pcr_jitter_ms: float = 0.0
    section_buffers: Dict[int, bytes] = field(default_factory=dict)
    last_video_frame: Optional[bytes] = None


STREAM_TYPE_VIDEO = {0x01, 0x02, 0x1B, 0x24, 0x10}
STREAM_TYPE_AUDIO = {0x03, 0x04, 0x0F, 0x11, 0x81, 0x82, 0x06}

PAT_PID = 0x0000
CAT_PID = 0x0001
SDT_PID = 0x0011
EIT_PID = 0x0012
NULL_PID = 0x1FFF


def _dvb_decode_string(data: bytes) -> str:
    if not data:
        return ""
    first = data[0]
    if first < 0x20:
        text = data[1:]
        if first == 0x15:
            try:
                return text.decode("utf-8", errors="replace")
            except Exception:
                return text.decode("latin-1", errors="replace")
        elif first in (0x01, 0x02, 0x03, 0x04, 0x05):
            return text.decode("latin-1", errors="replace")
        else:
            return text.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def _bcd_to_int(b: int) -> int:
    return (b >> 4) * 10 + (b & 0x0F)


class TSParser:
    SYNC_BYTE = 0x47
    PACKET_SIZE = 188

    def __init__(self, channel_id: str):
        self.state = TSParserState(channel_id=channel_id)

    @property
    def service_name(self) -> str:
        return self.state.service_name

    @property
    def event_name(self) -> str:
        return self.state.event_name

    @property
    def video_pid(self) -> int:
        return self.state.video_pid

    @property
    def audio_pid(self) -> int:
        return self.state.audio_pid

    @property
    def cc_errors(self) -> int:
        return self.state.cc_errors

    @property
    def pcr_jitter_ms(self) -> float:
        return self.state.pcr_jitter_ms

    def reset_cc_errors(self):
        self.state.cc_errors = 0

    def feed(self, data: bytes) -> List[TSPacket]:
        packets = []
        length = len(data)
        i = 0
        while i <= length - self.PACKET_SIZE:
            if data[i] == self.SYNC_BYTE:
                pkt = self._parse_packet(data[i:i + self.PACKET_SIZE])
                if pkt is not None:
                    self._process_packet(pkt)
                    packets.append(pkt)
                i += self.PACKET_SIZE
            else:
                i += 1
        return packets

    def _parse_packet(self, raw: bytes) -> Optional[TSPacket]:
        if len(raw) < 4:
            return None
        h = struct.unpack(">I", raw[:4])[0]
        transport_error = bool((h >> 23) & 1)
        payload_unit_start = bool((h >> 22) & 1)
        pid = (h >> 8) & 0x1FFF
        afc = (h >> 4) & 0x3
        cc = h & 0xF

        has_adaptation = bool(afc & 0x2)
        has_payload = bool(afc & 0x1)

        offset = 4
        adaptation = b""
        payload = b""

        if has_adaptation and offset < self.PACKET_SIZE:
            af_len = raw[offset]
            offset += 1
            if af_len > 0:
                adaptation = raw[offset:offset + af_len]
                offset += af_len

        if has_payload and offset < self.PACKET_SIZE:
            payload = raw[offset:]

        pcr = None
        if has_adaptation and len(adaptation) >= 6:
            flags = adaptation[0] if len(adaptation) > 0 else 0
            if flags & 0x10:
                b = adaptation[1:7]
                if len(b) >= 6:
                    pcr_base = (
                        (b[0] << 25) | (b[1] << 17) | (b[2] << 9) | (b[3] << 1) | ((b[4] >> 7) & 1)
                    )
                    pcr_ext = ((b[4] & 0x01) << 8) | b[5]
                    pcr = pcr_base * 300 + pcr_ext

        return TSPacket(
            pid=pid,
            cc=cc,
            payload_unit_start=payload_unit_start,
            has_payload=has_payload,
            has_adaptation=has_adaptation,
            payload=payload,
            adaptation=adaptation,
            pcr=pcr,
            transport_error=transport_error,
        )

    def _check_cc(self, pid: int, cc: int):
        if pid == NULL_PID or not self.state.pid_cc:
            pass
        if pid in self.state.pid_cc:
            expected = (self.state.pid_cc[pid] + 1) % 16
            if cc != expected and not (cc == self.state.pid_cc[pid]):
                self.state.cc_errors += 1
        self.state.pid_cc[pid] = cc

    def _process_packet(self, pkt: TSPacket):
        if pkt.transport_error or pkt.pid == NULL_PID:
            return
        self._check_cc(pkt.pid, pkt.cc)
        if pkt.pcr is not None and pkt.pid == self.state.pcr_pid:
            self._update_pcr_jitter(pkt.pcr)
        if not pkt.has_payload:
            return
        if pkt.pid == PAT_PID:
            self._accumulate_section(pkt.pid, pkt.payload, pkt.payload_unit_start)
        elif pkt.pid in self.state.pmt_pids:
            self._accumulate_section(pkt.pid, pkt.payload, pkt.payload_unit_start)
        elif pkt.pid == SDT_PID:
            self._accumulate_section(pkt.pid, pkt.payload, pkt.payload_unit_start)
        elif pkt.pid == EIT_PID:
            self._accumulate_section(pkt.pid, pkt.payload, pkt.payload_unit_start)

    def _accumulate_section(self, pid: int, payload: bytes, unit_start: bool):
        if unit_start:
            if not payload:
                return
            pointer = payload[0]
            self.state.section_buffers[pid] = payload[1 + pointer:]
        else:
            if pid in self.state.section_buffers:
                self.state.section_buffers[pid] += payload

        buf = self.state.section_buffers.get(pid, b"")
        if len(buf) < 3:
            return
        section_length = ((buf[1] & 0x0F) << 8) | buf[2]
        total = 3 + section_length
        if len(buf) >= total:
            self._parse_section(pid, buf[:total])
            self.state.section_buffers[pid] = buf[total:]

    def _parse_section(self, pid: int, data: bytes):
        if len(data) < 3:
            return
        table_id = data[0]
        if pid == PAT_PID and table_id == 0x00:
            self._parse_pat(data)
        elif pid in self.state.pmt_pids and table_id == 0x02:
            self._parse_pmt(data)
        elif pid == SDT_PID and table_id in (0x42, 0x46):
            self._parse_sdt(data)
        elif pid == EIT_PID and table_id in (0x4E, 0x4F, 0x50, 0x51):
            self._parse_eit(data)

    def _parse_pat(self, data: bytes):
        if len(data) < 8:
            return
        section_length = ((data[1] & 0x0F) << 8) | data[2]
        end = 3 + section_length - 4
        i = 8
        while i + 3 < end:
            program_num = (data[i] << 8) | data[i + 1]
            pmt_pid = ((data[i + 2] & 0x1F) << 8) | data[i + 3]
            if program_num != 0:
                self.state.pat[program_num] = pmt_pid
                self.state.pmt_pids.add(pmt_pid)
            i += 4

    def _parse_pmt(self, data: bytes):
        if len(data) < 12:
            return
        section_length = ((data[1] & 0x0F) << 8) | data[2]
        end = 3 + section_length - 4
        pcr_pid = ((data[8] & 0x1F) << 8) | data[9]
        self.state.pcr_pid = pcr_pid
        program_info_length = ((data[10] & 0x0F) << 8) | data[11]
        i = 12 + program_info_length
        while i + 4 < end:
            stream_type = data[i]
            es_pid = ((data[i + 1] & 0x1F) << 8) | data[i + 2]
            es_info_length = ((data[i + 3] & 0x0F) << 8) | data[i + 4]
            if stream_type in STREAM_TYPE_VIDEO and self.state.video_pid == -1:
                self.state.video_pid = es_pid
            elif stream_type in STREAM_TYPE_AUDIO and self.state.audio_pid == -1:
                self.state.audio_pid = es_pid
            i += 5 + es_info_length

    def _parse_sdt(self, data: bytes):
        if len(data) < 11:
            return
        section_length = ((data[1] & 0x0F) << 8) | data[2]
        end = 3 + section_length - 4
        i = 11
        while i + 4 < end:
            if i + 5 > len(data):
                break
            descriptors_loop_length = ((data[i + 3] & 0x0F) << 8) | data[i + 4]
            j = i + 5
            desc_end = j + descriptors_loop_length
            while j + 1 < desc_end and j + 1 < len(data):
                desc_tag = data[j]
                desc_len = data[j + 1]
                desc_data = data[j + 2:j + 2 + desc_len]
                if desc_tag == 0x48 and len(desc_data) >= 3:
                    provider_len = desc_data[1]
                    name_offset = 2 + provider_len
                    if name_offset < len(desc_data):
                        name_len = desc_data[name_offset]
                        name_data = desc_data[name_offset + 1:name_offset + 1 + name_len]
                        self.state.service_name = _dvb_decode_string(name_data)
                j += 2 + desc_len
            i += 5 + descriptors_loop_length

    def _parse_eit(self, data: bytes):
        if len(data) < 14:
            return
        section_length = ((data[1] & 0x0F) << 8) | data[2]
        end = 3 + section_length - 4
        i = 14
        while i + 11 < end:
            descriptors_loop_length = ((data[i + 10] & 0x0F) << 8) | data[i + 11]
            j = i + 12
            desc_end = j + descriptors_loop_length
            while j + 1 < desc_end and j + 1 < len(data):
                desc_tag = data[j]
                desc_len = data[j + 1]
                desc_data = data[j + 2:j + 2 + desc_len]
                if desc_tag == 0x4D and len(desc_data) >= 4:
                    event_name_len = desc_data[3]
                    event_name_data = desc_data[4:4 + event_name_len]
                    self.state.event_name = _dvb_decode_string(event_name_data)
                j += 2 + desc_len
            i += 12 + descriptors_loop_length

    def _update_pcr_jitter(self, pcr: int):
        now = time.monotonic()
        if self.state.last_pcr is not None and self.state.last_pcr_time is not None:
            pcr_diff = pcr - self.state.last_pcr
            if pcr_diff < 0:
                pcr_diff += (1 << 33) * 300
            expected_diff_27mhz = (now - self.state.last_pcr_time) * 27_000_000
            if expected_diff_27mhz > 0:
                jitter_ticks = abs(pcr_diff - expected_diff_27mhz)
                self.state.pcr_jitter_ms = jitter_ticks / 27_000.0
        self.state.last_pcr = pcr
        self.state.last_pcr_time = now

    def get_latest_video_payload(self) -> Optional[bytes]:
        return self.state.last_video_frame
