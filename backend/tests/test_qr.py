"""app.qr（零依赖二维码生成器）的测试。

一、用公开样例校验关键中间结果：
    - RS 纠错码字：ISO/IEC 18004 附录 I 的 "01234567"（1-M）编码示例；
      thonky.com QR Code Tutorial 的 "HELLO WORLD"（1-M）示例；
    - RS 生成多项式（ISO/IEC 18004 附录 A）；
    - 格式信息位串（纠错等级 M、掩码 0–7；掩码 5 即 ISO/IEC 18004 附录 C 的示例）；
    - 版本信息位串（ISO/IEC 18004 附录 D 表 D.1，7–10 版）；
    - 校正图形位置（附录 E 表 E.1）、各版本码字数 / 剩余位 / 字节容量（表 1、表 7、表 9）。
二、最小解码自检：在测试里独立实现「功能图形结构检查 → 读版本/格式信息 → 去掩码 →
    按 zigzag 顺序读码字 → 解交织 → RS 校验子 → 解析字节模式」，
    并与编码时的数据码字、原文比对。它只是结构自检，不能代替真实扫码验证。
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import pytest

from app import qr

# ============================================================================
# 公开样例与标准表格
# ============================================================================

# ISO/IEC 18004 附录 I："01234567"，版本 1，纠错等级 M（数字模式）。
ISO_01234567_DATA = [
    0b00010000, 0b00100000, 0b00001100, 0b01010110, 0b01100001, 0b10000000, 0b11101100, 0b00010001,
    0b11101100, 0b00010001, 0b11101100, 0b00010001, 0b11101100, 0b00010001, 0b11101100, 0b00010001,
]  # fmt: skip
ISO_01234567_ECC = [
    0b10100101, 0b00100100, 0b11010100, 0b11000001, 0b11101101,
    0b00110110, 0b11000111, 0b10000111, 0b00101100, 0b01010101,
]  # fmt: skip

# thonky.com QR Code Tutorial："HELLO WORLD"，1-M（字母数字模式）。
HELLO_WORLD_1M_DATA = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
HELLO_WORLD_1M_ECC = [196, 35, 39, 119, 235, 215, 231, 226, 93, 23]

# 生成多项式各项系数的 α 指数，最高次在前（ISO/IEC 18004 附录 A）。
GENERATOR_ALPHA_EXPONENTS = {
    2: [0, 25, 1],
    7: [0, 87, 229, 146, 149, 238, 102, 21],
    10: [0, 251, 67, 46, 61, 118, 70, 64, 94, 32, 45],
    16: [0, 120, 104, 107, 109, 102, 161, 76, 3, 91, 191, 147, 169, 182, 194, 225, 120],
}

# 纠错等级 M 的 15 位格式信息（已异或 101010000010010）。
FORMAT_M = {
    0: "101010000010010",
    1: "101000100100101",
    2: "101111001111100",
    3: "101101101001011",
    4: "100010111111001",
    5: "100000011001110",  # ISO/IEC 18004 附录 C：数据 00101，BCH 0011011100
    6: "100111110010111",
    7: "100101010100000",
}

# 18 位版本信息（ISO/IEC 18004 附录 D 表 D.1：07C94、085BC、09A99、0A4D3）。
VERSION_INFO = {
    7: "000111110010010100",
    8: "001000010110111100",
    9: "001001101010011001",
    10: "001010010011010011",
}

# ISO/IEC 18004 表 1（总码字数、剩余位）、表 9 / 表 7（纠错等级 M）。
TOTAL_CODEWORDS = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242, 9: 292, 10: 346}
REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}
DATA_CODEWORDS_M = {1: 16, 2: 28, 3: 44, 4: 64, 5: 86, 6: 108, 7: 124, 8: 154, 9: 182, 10: 216}
ECC_PER_BLOCK_M = {1: 10, 2: 16, 3: 26, 4: 18, 5: 24, 6: 16, 7: 18, 8: 22, 9: 22, 10: 26}
NUM_BLOCKS_M = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 4, 7: 4, 8: 4, 9: 5, 10: 5}
BYTE_CAPACITY_M = {1: 14, 2: 26, 3: 42, 4: 62, 5: 84, 6: 106, 7: 122, 8: 152, 9: 180, 10: 213}
ALIGNMENT_ANNEX_E = {1: [], 2: [6, 18], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 10: [6, 28, 50]}

# 覆盖 20 / 60 / 68 / 120 / 200 字节的 URL，以及一段中文（UTF-8 多字节）。
URL_20 = "http://10.0.0.2/p/01"
URL_60 = "http://192.168.1.23:5173/p?mode=first&code=P-0101&t=20260925"
URL_68 = "http://192.168.1.23:5173/p?mode=follow_up&parent=enc_xxx&code=P-0101"
URL_120 = (
    "http://192.168.1.23:5173/p?mode=follow_up&parent=enc_3f9a1c2b7d4e&code=P-0101"
    "&visit=2026-09-25&lang=zh-CN&src=clinic_qr1"
)
URL_200 = URL_120 + "&dept=spine&doctor=D-0007&note=recheck_in_2w&sig=9c1e5a7b3d2f4e6a8b0c1d2e3f4a5b6"
CJK_TEXT = "体迹 AI 复诊码：请在就诊前扫码补充症状变化（P-0101）"

# (文本, UTF-8 字节数, 期望版本)
CASES = [
    (URL_20, 20, 2),
    (URL_60, 60, 4),
    (URL_68, 68, 5),
    (URL_120, 120, 7),
    (URL_200, 200, 10),
    (CJK_TEXT, 73, 5),
    ("", 0, 1),
]
CASE_IDS = ["url20", "url60", "url68", "url120", "url200", "cjk", "empty"]


# ============================================================================
# 测试侧独立实现的最小解码器（只读 encode() 产出的矩阵，不调用 app.qr 的内部函数）
# ============================================================================


def _gf_tables() -> tuple[list[int], list[int]]:
    exp, log = [0] * 255, [0] * 256
    x = 1
    for i in range(255):
        exp[i], log[x] = x, i
        x = (x << 1) ^ (0x11D if x & 0x80 else 0)
    return exp, log


GF_EXP, GF_LOG = _gf_tables()


def gf_mul(a: int, b: int) -> int:
    return 0 if a == 0 or b == 0 else GF_EXP[(GF_LOG[a] + GF_LOG[b]) % 255]


def gf2_mod(value: int, generator: int) -> int:
    while value.bit_length() >= generator.bit_length():
        value ^= generator << (value.bit_length() - generator.bit_length())
    return value


# ISO/IEC 18004 表 10，i = 行，j = 列
MASKS = [
    lambda i, j: (i + j) % 2 == 0,
    lambda i, j: i % 2 == 0,
    lambda i, j: j % 3 == 0,
    lambda i, j: (i + j) % 3 == 0,
    lambda i, j: ((i // 2) + (j // 3)) % 2 == 0,
    lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    lambda i, j: ((i * j) % 3 + (i + j) % 2) % 2 == 0,
]

FINDER = ["1111111", "1000001", "1011101", "1011101", "1011101", "1000001", "1111111"]

# 第一份格式信息的位置，按 bit 14（最高位）→ bit 0 排列：第 8 行自左向右（跳过第 6 列），
# 再沿第 8 列自下而上（跳过第 6 行）。
FORMAT_COPY_1 = [
    (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
    (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
]  # fmt: skip


def format_copy_2(size: int) -> list[tuple[int, int]]:
    """第二份：第 8 列自下而上 7 位（bit 14→8），再第 8 行自左向右 8 位（bit 7→0）。"""
    return [(size - 1 - k, 8) for k in range(7)] + [(8, size - 8 + k) for k in range(8)]


def alignment_positions(version: int) -> list[int]:
    """附录 E 表 E.1 的闭式写法：第一个是 6，其余从 size−7 起按固定步长往回排。"""
    if version == 1:
        return []
    size = 4 * version + 17
    num = version // 7 + 2
    step = (version * 8 + num * 3 + 5) // (num * 4 - 4) * 2
    return [6] + [size - 7 - k * step for k in range(num - 2, -1, -1)]


def alignment_centers(version: int) -> list[tuple[int, int]]:
    pos = alignment_positions(version)
    if not pos:
        return []
    overlap_finders = {(pos[0], pos[0]), (pos[0], pos[-1]), (pos[-1], pos[0])}
    return [(r, c) for r in pos for c in pos if (r, c) not in overlap_finders]


def function_mask(version: int) -> list[list[bool]]:
    size = 4 * version + 17
    f = [[False] * size for _ in range(size)]

    def block(r0: int, c0: int, h: int, w: int) -> None:
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                f[r][c] = True

    block(0, 0, 9, 9)  # 左上：定位图形 + 分隔符 + 格式信息
    block(0, size - 8, 9, 8)  # 右上：定位图形 + 分隔符 + 格式信息
    block(size - 8, 0, 8, 9)  # 左下：定位图形 + 分隔符 + 格式信息 + 暗模块
    for k in range(size):  # 时序图形
        f[6][k] = f[k][6] = True
    for r0, c0 in alignment_centers(version):
        block(r0 - 2, c0 - 2, 5, 5)
    if version >= 7:  # 版本信息
        block(0, size - 11, 6, 3)
        block(size - 11, 0, 3, 6)
    return f


def zigzag(size: int, func: list[list[bool]]) -> list[tuple[int, int]]:
    """数据模块的读取顺序：从右下角起两列一组，上下往返，跳过第 6 列。"""
    order = []
    col, upward = size - 1, True
    while col > 0:
        if col == 6:
            col = 5
        for r in range(size - 1, -1, -1) if upward else range(size):
            for c in (col, col - 1):
                if not func[r][c]:
                    order.append((r, c))
        col, upward = col - 2, not upward
    return order


def read_bits(grid: list[list[int]], coords) -> int:
    value = 0
    for r, c in coords:
        value = (value << 1) | grid[r][c]
    return value


def check_function_patterns(grid: list[list[int]], version: int) -> None:
    size = len(grid)
    for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
        for dr in range(7):
            for dc in range(7):
                assert grid[r0 + dr][c0 + dc] == int(FINDER[dr][dc]), ("定位图形", r0, c0)
    for k in range(8):  # 分隔符全为浅色
        assert grid[7][k] == grid[k][7] == 0
        assert grid[7][size - 1 - k] == grid[k][size - 8] == 0
        assert grid[size - 8][k] == grid[size - 1 - k][7] == 0
    for k in range(8, size - 8):  # 时序图形
        assert grid[6][k] == grid[k][6] == (1 if k % 2 == 0 else 0)
    for r0, c0 in alignment_centers(version):
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                expect = 0 if max(abs(dr), abs(dc)) == 1 else 1
                assert grid[r0 + dr][c0 + dc] == expect, ("校正图形", r0, c0)
    assert grid[4 * version + 9][8] == 1  # 暗模块


def deinterleave(codewords: list[int], version: int) -> tuple[list[list[int]], list[list[int]]]:
    total, nblocks, ecc_len = len(codewords), NUM_BLOCKS_M[version], ECC_PER_BLOCK_M[version]
    n_short = nblocks - total % nblocks
    data_lens = [total // nblocks - ecc_len + (0 if b < n_short else 1) for b in range(nblocks)]
    it = iter(codewords)
    data: list[list[int]] = [[] for _ in range(nblocks)]
    for k in range(max(data_lens)):
        for b in range(nblocks):
            if k < data_lens[b]:
                data[b].append(next(it))
    ecc: list[list[int]] = [[] for _ in range(nblocks)]
    for _ in range(ecc_len):
        for b in range(nblocks):
            ecc[b].append(next(it))
    assert next(it, None) is None
    return data, ecc


def syndromes(block: list[int], n: int) -> list[int]:
    """码字多项式在 α^0…α^(n−1) 处的取值；合法 RS 码字应全部为 0。"""
    out = []
    for j in range(n):
        s = 0
        for cw in block:
            s = gf_mul(s, GF_EXP[j]) ^ cw
        out.append(s)
    return out


def parse_byte_mode(data: list[int], version: int) -> bytes:
    bits = "".join(f"{b:08b}" for b in data)
    assert bits[:4] == "0100", "模式指示符应为字节模式"
    cc = 8 if version <= 9 else 16
    n = int(bits[4 : 4 + cc], 2)
    pos = 4 + cc
    payload = bytes(int(bits[pos + 8 * k : pos + 8 * k + 8], 2) for k in range(n))
    pos += 8 * n
    term = min(4, len(bits) - pos)
    assert bits[pos : pos + term] == "0" * term, "终止符"
    pos += term
    byte_end = -(-pos // 8) * 8
    assert bits[pos:byte_end] == "0" * (byte_end - pos), "补齐到字节边界"
    rest = data[byte_end // 8 :]
    assert rest == [(0xEC, 0x11)[k % 2] for k in range(len(rest))], "填充码字"
    return payload


def decode(modules) -> dict:
    grid = [[1 if v else 0 for v in row] for row in modules]
    size = len(grid)
    assert all(len(row) == size for row in grid)
    assert size % 4 == 1 and 21 <= size <= 57
    version = (size - 17) // 4
    check_function_patterns(grid, version)

    if version >= 7:
        top_right = sum(grid[k // 3][size - 11 + k % 3] << k for k in range(18))
        bottom_left = sum(grid[size - 11 + k % 3][k // 3] << k for k in range(18))
        assert top_right == bottom_left
        assert top_right >> 12 == version
        assert gf2_mod(version << 12, 0x1F25) == top_right & 0xFFF

    fmt1 = read_bits(grid, FORMAT_COPY_1)
    fmt2 = read_bits(grid, format_copy_2(size))
    assert fmt1 == fmt2, "两份格式信息不一致"
    fmt = fmt1 ^ 0b101010000010010
    assert gf2_mod((fmt >> 10) << 10, 0x537) == fmt & 0x3FF, "格式信息 BCH 校验失败"
    ecl, mask = fmt >> 13, (fmt >> 10) & 0b111
    assert ecl == 0b00, "纠错等级应为 M"

    func = function_mask(version)
    cond = MASKS[mask]
    bits = [grid[r][c] ^ int(cond(r, c)) for r, c in zigzag(size, func)]
    n = len(bits) // 8
    assert n == TOTAL_CODEWORDS[version]
    assert len(bits) - 8 * n == REMAINDER_BITS[version]
    assert not any(bits[8 * n :]), "剩余位去掩码后应为 0"
    codewords = [int("".join(map(str, bits[8 * k : 8 * k + 8])), 2) for k in range(n)]

    data_blocks, ecc_blocks = deinterleave(codewords, version)
    for d, e in zip(data_blocks, ecc_blocks):
        assert syndromes(d + e, len(e)) == [0] * len(e), "RS 校验子不为 0"
    data = [b for block in data_blocks for b in block]
    return {
        "version": version,
        "mask": mask,
        "codewords": codewords,
        "data_codewords": data,
        "payload": parse_byte_mode(data, version),
    }


# ============================================================================
# 一、公开样例：关键中间结果
# ============================================================================


@pytest.mark.parametrize("degree", sorted(GENERATOR_ALPHA_EXPONENTS))
def test_rs_generator_polynomial_matches_annex_a(degree):
    coefs = qr.rs_generator(degree)
    assert [GF_LOG[c] for c in coefs] == GENERATOR_ALPHA_EXPONENTS[degree]


def test_rs_ecc_iso_annex_i_01234567():
    assert qr.rs_ecc(ISO_01234567_DATA, 10) == ISO_01234567_ECC


def test_rs_ecc_hello_world_1m():
    assert qr.rs_ecc(HELLO_WORLD_1M_DATA, 10) == HELLO_WORLD_1M_ECC


def test_rs_ecc_codeword_has_zero_syndromes():
    data = list(range(1, 44))
    ecc = qr.rs_ecc(data, 26)
    assert syndromes(data + ecc, 26) == [0] * 26


@pytest.mark.parametrize("mask", range(8))
def test_format_bits_level_m(mask):
    assert f"{qr.format_bits(mask):015b}" == FORMAT_M[mask]


@pytest.mark.parametrize("version", sorted(VERSION_INFO))
def test_version_bits_annex_d(version):
    assert f"{qr.version_bits(version):018b}" == VERSION_INFO[version]


def test_version_bits_only_for_7_and_up():
    with pytest.raises(ValueError):
        qr.version_bits(6)


@pytest.mark.parametrize("version", range(1, 11))
def test_version_tables(version):
    # 校正图形位置：模块查表 = 闭式公式；并抽查附录 E 原表
    assert list(qr._ALIGNMENT_POSITIONS[version]) == alignment_positions(version)
    if version in ALIGNMENT_ANNEX_E:
        assert alignment_positions(version) == ALIGNMENT_ANNEX_E[version]
    # 分组表（表 9）与总码字数、数据码字数、纠错码字数一致
    ecc_len, groups = qr._EC_BLOCKS_M[version]
    assert ecc_len == ECC_PER_BLOCK_M[version]
    assert sum(count for count, _ in groups) == NUM_BLOCKS_M[version]
    assert sum(count * length for count, length in groups) == DATA_CODEWORDS_M[version]
    assert DATA_CODEWORDS_M[version] + ecc_len * NUM_BLOCKS_M[version] == TOTAL_CODEWORDS[version]
    assert qr.byte_capacity(version) == BYTE_CAPACITY_M[version]
    # 功能图形之外的模块数 = 总码字数 × 8 + 剩余位（模块实现与测试侧独立实现各算一遍）
    expected_free = TOTAL_CODEWORDS[version] * 8 + REMAINDER_BITS[version]
    assert sum(not f for row in function_mask(version) for f in row) == expected_free
    _, func = qr._function_patterns(version)
    assert func == function_mask(version)


def test_data_codewords_byte_mode_hello():
    # 手工推导：0100 | 00000101 | 'h' 'e' 'l' 'l' 'o' | 0000 → 再交替填充 0xEC/0x11
    expected = [0x40, 0x56, 0x86, 0x56, 0xC6, 0xC6, 0xF0] + [0xEC, 0x11] * 4 + [0xEC]
    assert qr.data_codewords(b"hello", 1) == expected


def test_data_codewords_v10_uses_16_bit_count():
    words = qr.data_codewords(b"a" * 200, 10)
    assert len(words) == 216
    bits = "".join(f"{w:08b}" for w in words)
    assert bits[:4] == "0100" and int(bits[4:20], 2) == 200


# ============================================================================
# 二、版本选择与容量
# ============================================================================


@pytest.mark.parametrize("version", range(1, 11))
def test_smallest_version_is_chosen(version):
    cap = BYTE_CAPACITY_M[version]
    assert qr.encode("a" * cap).version == version
    if version < 10:
        assert qr.encode("a" * (cap + 1)).version == version + 1


def test_too_long_raises_value_error():
    qr.qr_svg("a" * 213)  # 10-M 刚好装得下
    with pytest.raises(ValueError):
        qr.qr_svg("a" * 214)
    qr.encode("中" * 71)  # 213 字节
    with pytest.raises(ValueError):
        qr.encode("中" * 72)  # 216 字节


# ============================================================================
# 三、解码自检
# ============================================================================


@pytest.mark.parametrize(("text", "nbytes", "version"), CASES, ids=CASE_IDS)
def test_decode_roundtrip(text, nbytes, version):
    assert len(text.encode("utf-8")) == nbytes
    sym = qr.encode(text)
    assert sym.version == version
    assert sym.size == 4 * version + 17
    got = decode(sym.modules)
    assert got["version"] == sym.version
    assert got["mask"] == sym.mask
    assert got["codewords"] == list(sym.codewords)
    assert got["data_codewords"] == list(sym.data_codewords)
    assert got["payload"].decode("utf-8") == text


@pytest.mark.parametrize("mask", range(8))
@pytest.mark.parametrize("text", [URL_20, URL_120, URL_200], ids=["v2", "v7", "v10"])
def test_decode_every_mask(text, mask):
    sym = qr.encode(text, mask=mask)
    got = decode(sym.modules)
    assert got["mask"] == mask
    assert got["data_codewords"] == list(sym.data_codewords)
    assert got["payload"].decode("utf-8") == text


@pytest.mark.parametrize("text", [URL_20, URL_60, URL_68, URL_120], ids=["url20", "url60", "url68", "url120"])
def test_auto_mask_has_lowest_penalty(text):
    scores = [qr.penalty_score(qr.encode(text, mask=m).modules) for m in range(8)]
    auto = qr.encode(text)
    assert auto.mask == scores.index(min(scores))
    assert qr.penalty_score(auto.modules) == min(scores)


def test_invalid_mask_rejected():
    with pytest.raises(ValueError):
        qr.encode("x", mask=8)


# ============================================================================
# 四、惩罚规则
# ============================================================================


def test_penalty_rule_1_runs():
    assert qr._run_penalty("1111") == 0
    assert qr._run_penalty("11111") == 3
    assert qr._run_penalty("1111111") == 5
    assert qr._run_penalty("11111000000") == 3 + 4
    assert qr._run_penalty("10101010") == 0


def test_penalty_rule_3_finder_like():
    assert qr._finder_like_count("10111010000") == 1
    assert qr._finder_like_count("00001011101") == 1
    assert qr._finder_like_count("000010111010000") == 1  # 两侧都有浅色也只算一处
    assert qr._finder_like_count("1011101") == 1  # 符号外的静区视为浅色
    assert qr._finder_like_count("10111011101") == 2  # 重叠的两处
    assert qr._finder_like_count("11110111011111") == 0
    assert qr._finder_like_count("1101011101011") == 0  # 两侧各只有 ≤3 个浅色
    assert qr._finder_like_count("0101110100") == 1  # 左侧 1 个浅色 + 3 个静区模块 = 4 个浅色


def test_penalty_breakdown_small_matrices():
    all_dark = [[True] * 5 for _ in range(5)]
    # 规则 1：10 条线 × 3；规则 2：16 个 2×2 块 × 3；规则 4：100% 深色 → k=10
    assert qr.penalty_breakdown(all_dark) == (30, 48, 0, 100)
    checker = [[(r + c) % 2 == 0 for c in range(5)] for r in range(5)]
    assert qr.penalty_breakdown(checker) == (0, 0, 0, 0)
    # 56% 深色 → 落在 55%–60% → k=1
    grid = [[False] * 5 for _ in range(5)]
    cells = [(r, c) for r in range(5) for c in range(5)][:14]
    for r, c in cells:
        grid[r][c] = True
    assert qr.penalty_breakdown(grid)[3] == 10


# ============================================================================
# 五、SVG 输出
# ============================================================================

SVG_NS = "{http://www.w3.org/2000/svg}"
SEGMENT = re.compile(r"M(\d+) (\d+)h(\d+)v1h-(\d+)z")


def svg_dark_cells(d: str) -> tuple[set[tuple[int, int]], int]:
    cells: set[tuple[int, int]] = set()
    pos = segments = 0
    for m in SEGMENT.finditer(d):
        assert m.start() == pos, "path 里不应有多余内容"
        pos = m.end()
        x, y, w, back = map(int, m.groups())
        assert w == back >= 1
        for dx in range(w):
            assert (y, x + dx) not in cells
            cells.add((y, x + dx))
        segments += 1
    assert pos == len(d)
    return cells, segments


@pytest.mark.parametrize(("text", "nbytes", "version"), CASES[:5], ids=CASE_IDS[:5])
def test_svg_matches_matrix(text, nbytes, version):
    svg = qr.qr_svg(text)
    root = ET.fromstring(svg)  # 必须是合法 XML
    assert root.tag == f"{SVG_NS}svg"
    sym = qr.encode(text)
    dim = sym.size + 8
    assert root.get("viewBox") == f"0 0 {dim} {dim}"
    assert root.get("width") == root.get("height") == str(dim * 4)
    assert root.get("shape-rendering") == "crispEdges"
    (rect,) = root.findall(f"{SVG_NS}rect")
    assert rect.get("fill") == "#FFFFFF"
    (path,) = root.findall(f"{SVG_NS}path")
    assert path.get("fill") == "#16233B"
    cells, segments = svg_dark_cells(path.get("d"))
    expected = {(r + 4, c + 4) for r, row in enumerate(sym.modules) for c, v in enumerate(row) if v}
    assert cells == expected
    # 每行相邻深色模块已合并成最长的横条
    runs = sum(1 for row in sym.modules for c, v in enumerate(row) if v and (c == 0 or not row[c - 1]))
    assert segments == runs


def test_svg_options_and_escaping():
    svg = qr.qr_svg(URL_20, border=0, scale=10, dark='red" onload="x', light="none")
    root = ET.fromstring(svg)
    assert root.get("viewBox") == "0 0 25 25"
    assert root.get("width") == "250"
    assert "onload" not in root.attrib
    (path,) = root.findall(f"{SVG_NS}path")
    assert path.get("fill") == 'red" onload="x'  # 被转义成属性值，而不是注入新属性
    assert root.find(f"{SVG_NS}rect").get("fill") == "none"
    cells, _ = svg_dark_cells(path.get("d"))
    assert (0, 0) in cells  # border=0 时定位图形贴边


@pytest.mark.parametrize("kwargs", [{"border": -1}, {"scale": 0}, {"scale": 1.5}, {"border": "4"}])
def test_svg_rejects_bad_geometry(kwargs):
    with pytest.raises(ValueError):
        qr.qr_svg("x", **kwargs)


def test_non_str_rejected():
    with pytest.raises(TypeError):
        qr.qr_svg(b"bytes")  # type: ignore[arg-type]
