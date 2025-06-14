import base64
import hashlib
import json
import time
import asyncio
from urllib import parse
import re
import aiohttp

from typing import Awaitable, Callable, TypeVar, overload, Literal
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
base_url = "https://megacloud.blog"
T = TypeVar("T")


async def make_request(url: str, headers: dict, params: dict, func: Callable[[aiohttp.ClientResponse], Awaitable[T]]) -> T:
    async with aiohttp.ClientSession() as client:
        async with client.get(url, headers=headers, params=params) as resp:
            return await func(resp)


@overload
def _re(pattern: str, string: str, name: str, *, l: Literal[True]) -> list[str]: ...
@overload
def _re(pattern: str, string: str, name: str, *, l: Literal[False]) -> re.Match: ...


def _re(pattern: str, string: str, name: str, *, l: bool) -> re.Match | list[str]:
    if l:
        v = re.findall(pattern, string)

    else:
        v = re.search(pattern, string)

    if not v:
        raise ValueError(f"{name} not found")

    return v


def generate_bitwise_func(operation: str) -> Callable:
    operation = re.sub(r"[\w$]{2}", "args", operation)
    if any(i in operation for i in (">", "<")):
        v = operation.split()
        v[-1] = f"({v[-1]} & 31)"
        operation = " ".join(v)

    return lambda *args: eval(operation)


def get_bitwise_operations(script: str) -> dict[int, Callable]:
    bitwise_switchcase_pattern = r"\w\[\d+\]=\(function\([\w$]+\)[{\d\w$:\(\),= ]+;switch\([\w$]+\){([^}]+)}"
    bitwise_operation_pattern = r"case (\d+):([^;]+);break;"

    switchcase_section = _re(bitwise_switchcase_pattern, script, "bitwise switchcase section", l=False).group(1)

    funcs = {}

    for num, operation in _re(bitwise_operation_pattern, switchcase_section, "bitwise operation", l=True):
        funcs[int(num)] = generate_bitwise_func(operation.split("=")[1])

    return funcs


def generate_sequence(n: int) -> list[int]:
    res = [5, 8, 14, 11]
    if n <= 4:
        return res

    for i in range(2, n - 2):
        res.append(res[i] + i + 3 - (i % 2))

    return res


def get_array_slices(script: str) -> list[tuple[int, ...]]:
    func_pattern = r"\w\.[\w$_]{2}"
    pattern = rf"case\s(\d{{1,2}}):{func_pattern}\({func_pattern}\(\),\w{{3}},{func_pattern}\({func_pattern}\(\w{{3}},([\d\-]+),[\d\-]+\),[\d\-]+,([\d\-]+)\)\)"

    pairs = tuple(map(lambda t: tuple(map(int, t)), _re(pattern, script, "pairs", l=True)))
    order_map = {v: i for i, v in enumerate(generate_sequence(len(pairs)))}

    pairs = list(sorted(pairs, key=lambda t: order_map[t[0]]))

    return pairs


def shuffle_array(script: str, array: list[str]) -> list[str]:
    slices = get_array_slices(script)
    for _, array_idx, tail_idx in slices:
        array, tail = array[:array_idx], array[array_idx:]
        array = tail[:tail_idx] + array

    return array


def get_key_indexes(script: str) -> list[int]:
    func_pattern = r"\w{3}\.[\w$_]{2}"
    array_content_pattern = r'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    array_item_pattern = rf'({func_pattern}\([\w",\(\)]+\))|({func_pattern}\("?\d+"?,"?\d+"?,{func_pattern}\(\d+\)\))|(\d+)'
    indexes = []

    array_items = _re(array_content_pattern, script, "index array", l=True)[-1]

    for m in _re(array_item_pattern, array_items, "index array items", l=True):
        idx = m[0] or m[1] or m[2]

        if not idx.isdigit():
            idx = _re(r'"(\d+)"', idx, "index in index array item", l=False).group(1)

        indexes.append(int(idx))

    return indexes


def get_key_parts(script: str, string_array: list[str]) -> list[str]:
    func_pattern = r"[\w$]{3}\.[\w$]{2}"
    array_content_pattern = r'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'

    call1_pattern = rf'{func_pattern}\(\+?"?(\d+)"?\)'
    call2_pattern = rf'{func_pattern}\({func_pattern}\("?(\d+)"?,"?(\d+)"?\)\)'
    call3_pattern = rf'{func_pattern}\({func_pattern}\("?(\d+)"?,"?(\d+)"?,{func_pattern}\((\d)\){{3}}'

    array_items = _re(array_content_pattern, script, "key parts array items", l=True)[0]
    func_calls = re.split(r"(?<=\)),(?=\w)", array_items)

    bitwise = get_bitwise_operations(script)
    parts = []

    for fcall in func_calls:
        if m := re.match(call1_pattern, fcall):
            i = int(m.group(1))
            v = string_array[i]

            parts.append(v)

        elif m := re.match(call2_pattern, fcall) or re.match(call3_pattern, fcall):
            i1 = int(m.group(1))
            i2 = int(m.group(2))
            flag = int(m.group(3)) if len(m.groups()) == 3 else 0

            i = bitwise[flag](i1, i2)
            v = string_array[i]

            parts.append(v)

        else:
            raise ValueError(f"unmatched {fcall}")

    return parts


def derive_key_and_iv(password: bytes) -> tuple[bytes, bytes]:
    hashes = []
    digest = password

    for _ in range(3):
        hash = hashlib.md5(digest).digest()
        hashes.append(hash)
        digest = hash + password

    return hashes[0] + hashes[1], hashes[2]


def decrypt_sources(key: bytes, value: str) -> str:
    bs = AES.block_size
    encrypted = base64.b64decode(value)

    salt = encrypted[8:bs]
    data = encrypted[bs:]

    key, iv = derive_key_and_iv(key + salt)

    obj = AES.new(key, AES.MODE_CBC, iv)
    result = obj.decrypt(data)

    return unpad(result, AES.block_size).decode()


async def get_secret_key() -> bytes:
    script_url = f"{base_url}/js/player/a/v2/pro/embed-1.min.js"
    script_version = int(time.time())

    script = await make_request(script_url, {}, {"v": script_version}, lambda i: i.text())
    strings = ""

    xor_key_pattern = r"\)\('([\[\]\w%*!()#.:?,~\-$\'&;@=+\^/]+)'\)};"
    string_pattern = r"function \w{2}\(\){return \"([\w%*^!()#.:?,~\-$\'&;@=+\/]+)\";}"
    delim_pattern = r"\w{3}=\w\.[\w$_]{2}\(\w{3},'(.)'\);"

    xor_key = _re(xor_key_pattern, script, "xor key", l=False).group(1)
    char_sequence = parse.unquote(_re(string_pattern, script, "char sequence", l=False).group(1))
    delim = _re(delim_pattern, script, "delimiter", l=False).group(1)

    for i in range(len(char_sequence)):
        a = ord(char_sequence[i])
        b = ord(xor_key[i % len(xor_key)])

        idx = a ^ b
        strings += chr(idx)

    string_array = strings.split(delim)
    string_array = shuffle_array(script, string_array)

    keys = get_key_parts(script, string_array)
    indexes = get_key_indexes(script)

    key = "".join(keys[i] for i in indexes)

    return key.encode()


async def extract(embed_url: str) -> dict:
    headers = {
        "User-Agent": user_agent,
        "Referer": base_url,
        "Origin": base_url,
    }

    id = _re(r"embed-2/v2/e-1/([A-z0-9]+)\?", embed_url, "source id", l=False).group(1)
    get_src_url = f"{base_url}/embed-2/v2/e-1/getSources"

    resp = await make_request(get_src_url, headers, {"id": id}, lambda i: i.json())

    if not resp["sources"]:
        raise ValueError("no sources found")

    key = await get_secret_key()
    sources = json.loads(decrypt_sources(key, resp["sources"]))

    resp["sources"] = sources

    resp["intro"] = resp["intro"]["start"], resp["intro"]["end"]
    resp["outro"] = resp["outro"]["start"], resp["outro"]["end"]

    return resp


async def main():
    url = "https://megacloud.blog/embed-2/v2/e-1/BfnkwT8H9IHg?k=1"
    print(json.dumps(await extract(url), indent=4))


asyncio.run(main())
