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
    bitwise_operation_pattern = r"case (\d+):([\w\[\]\-+|><^* =$]+);break;"

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
    func_pattern = r"\w\.[\w$]{2}"
    pattern = rf"case\s(\d{{1,2}}):{func_pattern}\({func_pattern}\(\),[\w$]{{3}},{func_pattern}\({func_pattern}\([\w$]{{3}},([\d\-]+),[\d\-]+\),[\d\-]+,([\d\-]+)\)\)"

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


@overload
def get_key(script: str, string_array: list[str], *, return_parts: Literal[True]) -> list[str]: ...
@overload
def get_key(script: str, string_array: list[str], *, return_parts: Literal[False]) -> str: ...


def get_key(script: str, string_array: list[str], *, return_parts: bool) -> list[str] | str:
    func_pattern = r"[\w$]{3}\.[\w$]{2}"
    call1_pattern = rf'{func_pattern}\(\+?"?(\d+)"?\)'
    call2_pattern = rf'{func_pattern}\({func_pattern}\("?(\d+)"?,"?(\d+)"?\)\)'
    call3_pattern = rf'{func_pattern}\({func_pattern}\("?(\d+)"?,"?(\d+)"?,{func_pattern}\((\d)\){{3}}'

    bitwise = get_bitwise_operations(script)

    def _eval_fcall(fcall: str) -> str:
        if m := re.match(call1_pattern, fcall):
            i = int(m.group(1))
            v = string_array[i]

        elif m := re.match(call2_pattern, fcall) or re.match(call3_pattern, fcall):
            i1 = int(m.group(1))
            i2 = int(m.group(2))
            flag = int(m.group(3)) if len(m.groups()) == 3 else 0

            i = bitwise[flag](i1, i2)
            v = string_array[i]

        else:
            raise ValueError(f"unmatched {fcall}")

        return v

    if return_parts:
        array_content_pattern = rf'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'

        try:
            array_items = _re(array_content_pattern, script, "", l=True)[0]
        except ValueError:
            return []

        func_calls = re.split(r"(?<=\)),(?=\w)", array_items)
        parts = [_eval_fcall(fcall) for fcall in func_calls]

        return parts

    else:
        key_func_pattern = rf'var [\w$,]{{28,}};(?:{func_pattern}\(\+?"?\d+"?\);)?[\w$]+=([\w$.\(\)\+,"]+);'
        fcall = _re(key_func_pattern, script, "key function call", l=False).group(1)
        key = _eval_fcall(fcall).replace("-", "")

        if key.endswith("="):
            key = base64.b64decode(key).decode()

        return key


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


def _resolve_karr_iarr(script: str, string_array: list[str]) -> bytes:
    keys = get_key(script, string_array, return_parts=True)
    indexes = get_key_indexes(script)

    key = "".join(keys[i] for i in indexes)
    return key.encode()


def _resolve_key_in_iarr(script: str) -> bytes:
    indexes = get_key_indexes(script)
    key = "".join(chr(i) for i in indexes)

    return key.encode()


def _resolve_key_in_var(script: str, string_array: list[str]) -> bytes:
    key = get_key(script, string_array, return_parts=False)
    return key.encode()


def _resolve_64arr(script: str, string_array: list[str], map_arg: str, map_body: str) -> bytes:
    keys = get_key(script, string_array, return_parts=True)
    bitwise = get_bitwise_operations(script)

    func_pattern = r"\w{3}\.[\w$_]{2}"

    parse_int_pattern = rf'\w+\({map_arg},\+?"16"?\)'
    bitwise2_pattern = rf"{func_pattern}\((\w),(\w\))"
    bitwise3_pattern = rf'{func_pattern}\("?(\d+)"?,"?(\d+)"?,{func_pattern}\((\d)\){{2}}'

    set_def_flag_pattern = rf'{func_pattern}\(\+?"?(\d+)"?\)'

    raw_values = []
    if re.search(parse_int_pattern, map_body):
        raw_values = [int(k, 16) for k in keys]

    elif m := re.search(bitwise2_pattern, map_body):
        flag = _re(set_def_flag_pattern, map_body, "set flag func call", l=False).group(1)
        func = bitwise[flag]

        var_name = m.group(1) if m.group(1) != map_arg else m.group(2)
        var_value = _re(rf"\s+{var_name}=(\d+);", script, "bitwise static value", l=False).group(1)

        raw_values = [func(var_value, int(i)) for i in keys]

    # elif m := re.search(bitwise3_pattern, map_body):
    #     ...

    return "".join([chr(v) for v in raw_values]).encode()


def _resolve_key(script: str, string_array: list[str]) -> bytes:
    keygen_func_pattern = r"var [\w$,]{28,};.+?\w=\(\)=>{(.+?)};"
    map_pattern = r"\((\w)=>{(.+?return.+?;)"

    keygen_func = _re(keygen_func_pattern, script, "map function", l=False)
    keygen_body = keygen_func.group(1)

    try:
        map_func = _re(map_pattern, keygen_body, "map body", l=False)
        map_arg = map_func.group(1)
        map_body = map_func.group(2)

        string = map_body
        versions = {
            r"return \w\[\w\];": (_resolve_karr_iarr, script, string_array),
            r"return .+": (_resolve_64arr, script, string_array, map_arg, map_body),
        }

    except ValueError:
        string = keygen_body
        versions = {
            r"return \w\[|[\w$]+\(": (_resolve_key_in_var, script, string_array),
            r"return \w+\[": (_resolve_key_in_iarr, script),
        }

    for p, t in versions.items():
        if re.search(p, string):
            func = t[0]
            args = t[1:]

            return func(*args)


async def get_secret_key() -> bytes:
    script_url = f"{base_url}/js/player/a/v2/pro/embed-1.min.js"
    script_version = int(time.time())

    script = await make_request(script_url, {}, {"v": script_version}, lambda i: i.text())
    strings = ""

    xor_key_pattern = r"\)\('(.+)'\)};"
    string_pattern = r"function [\w$]{2}\(\){return \"(.+?)\";}"
    delim_pattern = r"[\w$]{3}=\w\.[\w$]{2}\([\w$]{3},'(.)'\);"

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

    key = _resolve_key(script, string_array)
    return key


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
    url = "https://megacloud.blog/embed-2/v2/e-1/n0SVutpGWsDC?k=1&autoPlay=1&oa=0&asi=1"
    print(json.dumps(await extract(url), indent=4))


asyncio.run(main())
