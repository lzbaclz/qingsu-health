"""零依赖的二维码（QR Code Model 2）生成器，输出 SVG。

编码参数固定：
- 字节模式，内容按 UTF-8 编码（不加 ECI 头；主流扫码器会自动识别 UTF-8，纯 ASCII 的 URL 不受影响）；
- 纠错等级 M；
- 在 1–10 版中自动选能装下的最小版本；10-M 最多 213 字节，超出抛 ValueError。

实现要点（依据 ISO/IEC 18004:2015）：
- GF(256) 上的 Reed-Solomon 纠错：本原多项式 x^8+x^4+x^3+x^2+1（0x11D），
  生成多项式 g(x) = (x − α^0)(x − α^1)…(x − α^(n−1))；
- 按表 9 分组，逐块计算纠错码字，再按列交织（先数据码字，后纠错码字）；
- 功能图形：定位图形 + 分隔符、时序图形、校正图形（附录 E 查表）、暗模块、
  格式信息（BCH(15,5)，生成多项式 0x537，异或掩码 0x5412）、
  版本信息（BCH(18,6)，生成多项式 0x1F25，仅 7 版及以上）；
- 码字从右下角开始两列一组、上下往返（zigzag）放置；
- 8 种掩码逐一尝试，按 4 条惩罚规则打分，取分数最低者（同分取编号小的）。

坐标约定：modules[row][col]，True 表示深色模块。

用法：
    from app.qr import qr_svg
    svg = qr_svg("http://192.168.1.23:5173/p?code=P-0101")
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import escape
from typing import Sequence

__all__ = ["MAX_VERSION", "QrSymbol", "byte_capacity", "encode", "qr_svg"]

MAX_VERSION = 10

# 格式信息里纠错等级的 2 位编码：L=01, M=00, Q=11, H=10
_ECL_M = 0b00

# 版本 -> (每块纠错码字数, ((块数, 每块数据码字数), ...))
# 出处：ISO/IEC 18004:2015 表 9，纠错等级 M。
_EC_BLOCKS_M: dict[int, tuple[int, tuple[tuple[int, int], ...]]] = {
    1: (10, ((1, 16),)),
    2: (16, ((1, 28),)),
    3: (26, ((1, 44),)),
    4: (18, ((2, 32),)),
    5: (24, ((2, 43),)),
    6: (16, ((4, 27),)),
    7: (18, ((4, 31),)),
    8: (22, ((2, 38), (2, 39))),
    9: (22, ((3, 36), (2, 37))),
    10: (26, ((4, 43), (1, 44))),
}

# 校正图形中心的行/列坐标，两两组合（去掉与三个定位图形重叠的三个组合）。
# 出处：ISO/IEC 18004:2015 附录 E 表 E.1。
_ALIGNMENT_POSITIONS: dict[int, tuple[int, ...]] = {
    1: (),
    2: (6, 18),
    3: (6, 22),
    4: (6, 26),
    5: (6, 30),
    6: (6, 34),
    7: (6, 22, 38),
    8: (6, 24, 42),
    9: (6, 26, 46),
    10: (6, 28, 50),
}

_FORMAT_GENERATOR = 0x537  # x^10 + x^8 + x^5 + x^4 + x^2 + x + 1
_FORMAT_XOR_MASK = 0x5412  # 101010000010010
_VERSION_GENERATOR = 0x1F25  # x^12 + x^11 + x^10 + x^9 + x^8 + x^5 + x^2 + 1

# 惩罚规则权重 N1–N4（ISO/IEC 18004:2015 7.8.3.1）
_N1, _N2, _N3, _N4 = 3, 3, 40, 10

Grid = list[list[bool]]


# ---------------------------------------------------------------------------
# GF(256) 与 Reed-Solomon
# ---------------------------------------------------------------------------


def _build_gf_tables() -> tuple[tuple[int, ...], tuple[int, ...]]:
    exp = [0] * 512  # 多存一倍，乘法时 log a + log b 不必取模
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]
    return tuple(exp), tuple(log)


_GF_EXP, _GF_LOG = _build_gf_tables()


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


@lru_cache(maxsize=None)
def rs_generator(degree: int) -> tuple[int, ...]:
    """g(x) = ∏_{i=0}^{degree-1} (x − α^i) 的系数，最高次在前（首项恒为 1）。"""
    if degree < 1:
        raise ValueError("degree 必须 ≥ 1")
    poly = [1]
    for i in range(degree):
        root = _GF_EXP[i]
        nxt = poly + [0]  # poly · x
        for j, coef in enumerate(poly):
            nxt[j + 1] ^= _gf_mul(coef, root)  # + poly · α^i（GF(2^8) 中减法即异或）
        poly = nxt
    return tuple(poly)


def rs_ecc(data: Sequence[int], degree: int) -> list[int]:
    """纠错码字：data(x)·x^degree 除以 g(x) 的余式，共 degree 个，最高次在前。"""
    divisor = rs_generator(degree)[1:]
    rem = [0] * degree
    for byte in data:
        if not 0 <= byte <= 0xFF:
            raise ValueError(f"码字越界：{byte}")
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i, coef in enumerate(divisor):
                rem[i] ^= _gf_mul(coef, factor)
    return rem


# ---------------------------------------------------------------------------
# 格式信息 / 版本信息（BCH）
# ---------------------------------------------------------------------------


def _bch_remainder(value: int, generator: int) -> int:
    """GF(2) 上 value 除以 generator 的余式（多项式都以整数的二进制位表示）。"""
    glen = generator.bit_length()
    while value.bit_length() >= glen:
        value ^= generator << (value.bit_length() - glen)
    return value


def format_bits(mask: int) -> int:
    """纠错等级 M + 给定掩码的 15 位格式信息（已异或 0x5412），bit 14 为最高位。"""
    if not 0 <= mask <= 7:
        raise ValueError("mask 只能是 0–7")
    data = (_ECL_M << 3) | mask
    return ((data << 10) | _bch_remainder(data << 10, _FORMAT_GENERATOR)) ^ _FORMAT_XOR_MASK


def version_bits(version: int) -> int:
    """18 位版本信息：6 位版本号 + 12 位 BCH 校验位（只有 7 版及以上才画进符号）。"""
    if not 7 <= version <= 40:
        raise ValueError("版本信息只存在于 7–40 版")
    return (version << 12) | _bch_remainder(version << 12, _VERSION_GENERATOR)


# ---------------------------------------------------------------------------
# 数据编码：字节模式、版本选择、填充、分块与交织
# ---------------------------------------------------------------------------


def _count_bits(version: int) -> int:
    """字节模式字符计数指示符的位数：1–9 版 8 位，10–26 版 16 位。"""
    return 8 if version <= 9 else 16


def _num_data_codewords(version: int) -> int:
    return sum(count * length for count, length in _EC_BLOCKS_M[version][1])


def byte_capacity(version: int) -> int:
    """该版本（纠错等级 M、字节模式）最多能装的字节数。"""
    return (_num_data_codewords(version) * 8 - 4 - _count_bits(version)) // 8


def _choose_version(num_bytes: int) -> int:
    for version in range(1, MAX_VERSION + 1):
        if num_bytes <= byte_capacity(version):
            return version
    raise ValueError(
        f"数据为 {num_bytes} 字节（UTF-8），超出 {MAX_VERSION}-M 版容量 {byte_capacity(MAX_VERSION)} 字节"
    )


def data_codewords(payload: bytes, version: int) -> list[int]:
    """模式指示符 0100 + 字符计数 + 数据 + 终止符 + 补到整字节 + 交替填充 0xEC/0x11。"""
    if len(payload) > byte_capacity(version):
        raise ValueError(f"{len(payload)} 字节装不进 {version}-M 版")
    capacity = _num_data_codewords(version)
    cap_bits = capacity * 8
    count_bits = _count_bits(version)

    acc, nbits = 0b0100, 4
    acc = (acc << count_bits) | len(payload)
    nbits += count_bits
    for byte in payload:
        acc = (acc << 8) | byte
    nbits += 8 * len(payload)

    terminator = min(4, cap_bits - nbits)  # 最多 4 个 0；剩余容量不足 4 位时截短
    acc <<= terminator
    nbits += terminator
    pad_bits = -nbits % 8  # 补 0 到字节边界
    acc <<= pad_bits
    nbits += pad_bits

    words = list(acc.to_bytes(nbits // 8, "big"))
    words.extend((0xEC, 0x11)[i % 2] for i in range(capacity - len(words)))
    return words


def _split_blocks(data: Sequence[int], version: int) -> list[list[int]]:
    blocks: list[list[int]] = []
    pos = 0
    for count, length in _EC_BLOCKS_M[version][1]:
        for _ in range(count):
            blocks.append(list(data[pos : pos + length]))
            pos += length
    if pos != len(data):
        raise ValueError(f"{version}-M 版需要 {pos} 个数据码字，实际 {len(data)} 个")
    return blocks


def interleave(data: Sequence[int], version: int) -> list[int]:
    """分块 → 逐块计算 RS 纠错码字 → 先按列交织数据码字，再按列交织纠错码字。"""
    ec_len = _EC_BLOCKS_M[version][0]
    blocks = _split_blocks(data, version)
    eccs = [rs_ecc(block, ec_len) for block in blocks]
    out: list[int] = []
    for i in range(max(len(block) for block in blocks)):
        out.extend(block[i] for block in blocks if i < len(block))  # 短块先取完
    for i in range(ec_len):
        out.extend(ecc[i] for ecc in eccs)
    return out


# ---------------------------------------------------------------------------
# 矩阵：功能图形、码字放置、掩码
# ---------------------------------------------------------------------------


def _draw_format(modules: Grid, bits: int, func: Grid | None = None) -> None:
    """画两份 15 位格式信息（bit 14 为最高位）和暗模块。"""
    size = len(modules)

    def put(r: int, c: int, dark: bool) -> None:
        modules[r][c] = dark
        if func is not None:
            func[r][c] = True

    def bit(i: int) -> bool:
        return bool((bits >> i) & 1)

    # 第一份，围绕左上定位图形：第 8 列自上而下放 bit 0–5（跳过第 6 行时序）、bit 6、bit 7，
    # 再沿第 8 行自右向左放 bit 8–14（跳过第 6 列时序）
    for i in range(6):
        put(i, 8, bit(i))
    put(7, 8, bit(6))
    put(8, 8, bit(7))
    put(8, 7, bit(8))
    for i in range(9, 15):
        put(8, 14 - i, bit(i))
    # 第二份：右上沿第 8 行自右向左放 bit 0–7；左下沿第 8 列自上而下放 bit 8–14
    for i in range(8):
        put(8, size - 1 - i, bit(i))
    for i in range(8, 15):
        put(size - 15 + i, 8, bit(i))
    put(size - 8, 8, True)  # 暗模块，位于 (4V+9, 8)


def _draw_version(modules: Grid, version: int, func: Grid | None = None) -> None:
    """画两份 18 位版本信息：右上 6 行×3 列，左下 3 行×6 列（互为转置），bit 0 为最低位。"""
    bits = version_bits(version)
    size = len(modules)
    for i in range(18):
        dark = bool((bits >> i) & 1)
        a, b = size - 11 + i % 3, i // 3
        for r, c in ((b, a), (a, b)):
            modules[r][c] = dark
            if func is not None:
                func[r][c] = True


def _function_patterns(version: int) -> tuple[Grid, Grid]:
    """画出全部功能图形，返回 (modules, is_function)。格式信息先按全 0 占位，选定掩码后重画。"""
    size = 4 * version + 17
    modules = [[False] * size for _ in range(size)]
    func = [[False] * size for _ in range(size)]

    def put(r: int, c: int, dark: bool) -> None:
        modules[r][c] = dark
        func[r][c] = True

    # 时序图形：第 6 行、第 6 列深浅交替，偶数位深色；与定位图形重叠的部分下面会被覆盖
    for i in range(size):
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)

    # 定位图形 7×7（中心 3×3 深、再一圈浅、最外圈深）+ 外侧 1 模块宽的浅色分隔符
    for cr, cc in ((3, 3), (3, size - 4), (size - 4, 3)):
        for dr in range(-4, 5):
            for dc in range(-4, 5):
                r, c = cr + dr, cc + dc
                if 0 <= r < size and 0 <= c < size:
                    put(r, c, max(abs(dr), abs(dc)) in (0, 1, 3))

    # 校正图形 5×5（中心深、一圈浅、外圈深）
    positions = _ALIGNMENT_POSITIONS[version]
    last = len(positions) - 1
    for i, r0 in enumerate(positions):
        for j, c0 in enumerate(positions):
            if (i, j) in ((0, 0), (0, last), (last, 0)):
                continue  # 与定位图形重叠
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    put(r0 + dr, c0 + dc, max(abs(dr), abs(dc)) != 1)

    _draw_format(modules, 0, func)  # 占位（含暗模块）
    if version >= 7:
        _draw_version(modules, version, func)
    return modules, func


def _place_codewords(modules: Grid, func: Grid, codewords: Sequence[int]) -> None:
    """从右下角开始，两列一组、上下往返（zigzag）放置码字比特，每个码字高位在前。"""
    size = len(modules)
    free = sum(1 for row in func for is_func in row if not is_func)
    if free // 8 != len(codewords):
        raise RuntimeError(f"可用数据模块 {free} 个，与码字数 {len(codewords)} 不匹配")
    total_bits = len(codewords) * 8
    i = 0
    upward = True
    right = size - 1
    while right >= 1:
        if right == 6:  # 第 6 列是纵向时序图形，整列跳过
            right = 5
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for c in (right, right - 1):
                if func[r][c]:
                    continue
                if i < total_bits:
                    modules[r][c] = bool((codewords[i >> 3] >> (7 - (i & 7))) & 1)
                    i += 1
                # 码字放完后剩下的模块是剩余位（remainder bits，0–7 个），保持浅色 0
        upward = not upward
        right -= 2
    if i != total_bits:
        raise RuntimeError("码字没有全部放入矩阵")


# 掩码条件（i = 行，j = 列），ISO/IEC 18004:2015 表 10
_MASK_CONDITIONS = (
    lambda i, j: (i + j) % 2 == 0,
    lambda i, j: i % 2 == 0,
    lambda i, j: j % 3 == 0,
    lambda i, j: (i + j) % 3 == 0,
    lambda i, j: (i // 2 + j // 3) % 2 == 0,
    lambda i, j: (i * j) % 2 + (i * j) % 3 == 0,
    lambda i, j: ((i * j) % 2 + (i * j) % 3) % 2 == 0,
    lambda i, j: ((i + j) % 2 + (i * j) % 3) % 2 == 0,
)


def _apply_mask(modules: Grid, func: Grid, mask: int) -> Grid:
    """返回新矩阵：只翻转非功能模块中满足掩码条件的模块。"""
    cond = _MASK_CONDITIONS[mask]
    size = len(modules)
    return [
        [modules[r][c] ^ (not func[r][c] and cond(r, c)) for c in range(size)]
        for r in range(size)
    ]


# ---------------------------------------------------------------------------
# 掩码惩罚（ISO/IEC 18004:2015 7.8.3.1，表 11）
# ---------------------------------------------------------------------------

_FINDER_LIKE = "1011101"  # 深:浅:深:浅:深 = 1:1:3:1:1


def _run_penalty(line: str) -> int:
    """规则 1：一行/一列里连续 5+i 个同色模块，罚 N1 + i。"""
    score = 0
    run = 1
    for k in range(1, len(line) + 1):
        if k < len(line) and line[k] == line[k - 1]:
            run += 1
            continue
        if run >= 5:
            score += _N1 + (run - 5)
        run = 1
    return score


def _finder_like_count(line: str) -> int:
    """规则 3：1:1:3:1:1 图形，前或后紧邻 4 个浅色模块（符号外的静区视为浅色），每处计一次。"""
    padded = "0000" + line + "0000"
    count = 0
    k = padded.find(_FINDER_LIKE)
    while k != -1:
        if padded[k - 4 : k] == "0000" or padded[k + 7 : k + 11] == "0000":
            count += 1
        k = padded.find(_FINDER_LIKE, k + 1)
    return count


def penalty_breakdown(modules: Sequence[Sequence[bool]]) -> tuple[int, int, int, int]:
    """返回 4 条规则各自的罚分 (N1 连续同色, N2 2×2 同色块, N3 类定位图形, N4 深浅比例)。"""
    size = len(modules)
    rows = ["".join("1" if dark else "0" for dark in row) for row in modules]
    cols = ["".join(row[c] for row in rows) for c in range(size)]
    lines = rows + cols

    p1 = sum(_run_penalty(line) for line in lines)
    # 规则 2：m×n 的同色块罚 N2·(m−1)·(n−1)，等价于逐个数（可重叠的）2×2 同色块
    p2 = _N2 * sum(
        1
        for r in range(size - 1)
        for c in range(size - 1)
        if rows[r][c] == rows[r][c + 1] == rows[r + 1][c] == rows[r + 1][c + 1]
    )
    p3 = _N3 * sum(_finder_like_count(line) for line in lines)
    # 规则 4：深色占比落在 50±5k% 到 50±5(k+1)% 之间，罚 N4·k，即 k = ⌊|深色% − 50| / 5⌋
    dark = sum(row.count("1") for row in rows)
    total = size * size
    p4 = _N4 * (abs(20 * dark - 10 * total) // total) if total else 0
    return p1, p2, p3, p4


def penalty_score(modules: Sequence[Sequence[bool]]) -> int:
    return sum(penalty_breakdown(modules))


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QrSymbol:
    version: int
    mask: int
    modules: tuple[tuple[bool, ...], ...]  # [row][col]，True 为深色，不含静区
    data_codewords: tuple[int, ...]  # 分块交织前的数据码字（不含纠错码字）
    codewords: tuple[int, ...]  # 交织后实际写入矩阵的全部码字（数据 + 纠错）

    @property
    def size(self) -> int:
        return len(self.modules)


def encode(data: str, *, mask: int | None = None) -> QrSymbol:
    """把字符串编码成二维码矩阵（字节模式 UTF-8、纠错等级 M、1–10 版）。

    mask 默认 None：8 种掩码都试，取惩罚分最低者；传 0–7 可强制指定（仅供测试/调试）。
    """
    if not isinstance(data, str):
        raise TypeError("data 必须是 str")
    if mask is not None and mask not in range(8):
        raise ValueError("mask 只能是 0–7 或 None")
    payload = data.encode("utf-8")
    version = _choose_version(len(payload))
    words = data_codewords(payload, version)
    final = interleave(words, version)

    base, func = _function_patterns(version)
    _place_codewords(base, func, final)

    best: tuple[int, int, Grid] | None = None
    for m in range(8) if mask is None else (mask,):
        grid = _apply_mask(base, func, m)
        _draw_format(grid, format_bits(m))
        score = penalty_score(grid)
        if best is None or score < best[0]:
            best = (score, m, grid)
    assert best is not None
    _, chosen, grid = best
    return QrSymbol(
        version=version,
        mask=chosen,
        modules=tuple(tuple(row) for row in grid),
        data_codewords=tuple(words),
        codewords=tuple(final),
    )


def _path_runs(modules: Sequence[Sequence[bool]], offset: int):
    """每行相邻的深色模块合并成一条横向长条：M x y h n v1 h-n z。"""
    for r, row in enumerate(modules):
        c = 0
        width = len(row)
        while c < width:
            if not row[c]:
                c += 1
                continue
            start = c
            while c < width and row[c]:
                c += 1
            n = c - start
            yield f"M{start + offset} {r + offset}h{n}v1h-{n}z"


def qr_svg(
    data: str,
    *,
    border: int = 4,
    scale: int = 4,
    dark: str = "#16233B",
    light: str = "#FFFFFF",
) -> str:
    """生成二维码 SVG 字符串。

    border：静区宽度（模块数，规范建议 ≥4）；scale：每个模块的像素数（决定 width/height）；
    dark/light：深色模块与背景颜色。viewBox 以模块为单位，可任意缩放。
    数据超出 10-M 版容量（213 字节 UTF-8）时抛 ValueError。
    """
    if isinstance(border, bool) or not isinstance(border, int) or border < 0:
        raise ValueError("border 必须是 ≥ 0 的整数")
    if isinstance(scale, bool) or not isinstance(scale, int) or scale < 1:
        raise ValueError("scale 必须是 ≥ 1 的整数")
    symbol = encode(data)
    dim = symbol.size + 2 * border
    px = dim * scale
    d = "".join(_path_runs(symbol.modules, border))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" '
        f'width="{px}" height="{px}" shape-rendering="crispEdges">'
        f'<rect width="{dim}" height="{dim}" fill="{escape(light)}"/>'
        f'<path fill="{escape(dark)}" d="{d}"/>'
        "</svg>"
    )
