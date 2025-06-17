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
from enum import StrEnum, IntEnum


user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
base_url = "https://megacloud.blog"
T = TypeVar("T")


class ResolverFlags(IntEnum):
    MAP = 1 << 0
    REVERSE = 1 << 1
    FROMCHARCODE = 1 << 2
    SLICE = 1 << 3
    FALLBACK = 1 << 4


class Patterns(StrEnum):
    _FUNC = r"[\w$]{3}\.[\w$]{2}"
    _FUNC2 = r"[\w$]\.[\w$]{2}"

    SOURCE_ID = r"embed-2/v2/e-1/([A-z0-9]+)\?"

    IDX = r'"(\d+)"'
    VAR = r"\s+{}=(\d+);"

    XOR_KEY = r"\)\('(.+)'\)};"
    STRING = r"function [\w$]{2}\(\){return \"(.+?)\";}"
    DELIMITER = r"[\w$]{3}=\w\.[\w$]{2}\([\w$]{3},'(.)'\);"

    BITWISE_SWITCHCASE = r"\w\[\d+\]=\(function\([\w$]+\)[{\d\w$:\(\),= ]+;switch\([\w$]+\){([^}]+)}"
    BITWISE_OPERATION = r"case (\d+):([\w\[\]\-+|><^* =$]+);break;"

    SLICES = rf"case\s(\d{{1,2}}):{_FUNC2}\({_FUNC2}\(\),[\w$]{{3}},{_FUNC2}\({_FUNC2}\([\w$]{{3}},([\d\-]+),[\d\-]+\),[\d\-]+,([\d\-]+)\)\)"

    _GET1_INDEX = r'+?"?(\d+)"?(?:( [|\-\+*><]+ "?\d+"?))?'
    GET1 = rf"{_FUNC}\(\{_GET1_INDEX}\)"
    GET2 = rf'{_FUNC}\({_FUNC}\("?(\d+)"?,"?(\d+)"?\)\)'
    GET3 = rf'{_FUNC}\({_FUNC}\("?(\d+)"?,"?(\d+)"?,{_FUNC}\((\d)\)\)\)'
    GET = f"{GET1}|{GET2}|{GET3}"

    INDEX_ARRAY_CONTENT = r'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    INDEX_ARRAY_ITEM = rf'({_FUNC}\([\w",\(\)]+\))|({_FUNC}\("?\d+"?,"?\d+"?,{_FUNC}\(\d+\)\))|(\d+)'

    KEY_ARRAY_CONTENT = rf'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    GET_KEY = rf'var [\w$,]{{28,}};(?:{_FUNC}\(\+?"?\d+"?\);)?[\w$]+=([\w$.\(\)\+,"]+);'

    KEYGEN = r"var [\w$,]{28,};.+?\w=\(\)=>{(.+?)};"
    MAP = r"\((\w)=>{(.+?return.+?;)"

    PARSE_INT = r'\w+\({},\+?"16"?\)'
    BITWISE2 = rf"{_FUNC}\((\w),(\w\))"
    BITWISE3 = rf'{_FUNC}\("?(\d+)"?,"?(\d+)"?,{_FUNC}\((\d)\)\)'
    SET_DEF_FLAG = rf'{_FUNC}\(\+?"?(\d+)"?\)'


class Resolvers:
    @staticmethod
    def _get_key(s: "Extractor") -> str:
        fcall = _re(Patterns.GET_KEY, s.script, l=False)
        args = _re(Patterns.GET, fcall.group(1), l=False)

        return s._get(args.groups()).replace("-", "")

    @staticmethod
    def _get_keys(s: "Extractor") -> list[str]:
        key_array_items = _re(Patterns.KEY_ARRAY_CONTENT, s.script, l=True)[0]
        func_calls = re.split(r"(?<=\)),(?=\w)", key_array_items)

        keys = []
        for fcall in func_calls:
            args = _re(Patterns.GET, fcall, l=False).groups()
            keys.append(s._get(args))

        return keys

    @classmethod
    def slice(cls, s: "Extractor") -> str:
        key = cls._get_key(s)
        if key.endswith("="):
            key = base64.b64decode(key).decode()

        return key

    @classmethod
    def map(cls, s: "Extractor") -> str:
        keys = cls._get_keys(s)
        indexes = s._get_indexes()

        key = "".join(keys[i] for i in indexes)
        return key

    @classmethod
    def from_charcode(cls, s: "Extractor") -> str:
        keys = cls._get_keys(s)
        bitwise = s.bitwise
        raw_values = []

        map_ = _re(Patterns.MAP, s.script, l=False)
        map_arg = map_.group(1)
        map_body = map_.group(2)

        if re.search(Patterns.PARSE_INT.format(map_arg), map_body):
            raw_values = [int(k, 16) for k in keys]

        elif m := re.search(Patterns.BITWISE2, map_body):
            flag = _re(Patterns.SET_DEF_FLAG, map_body, l=False).group(1)
            func = bitwise[flag]

            var_name = m.group(1) if m.group(1) != map_arg else m.group(2)
            var_value = _re(Patterns.VAR.format(var_name), s.script, l=False).group(1)

            raw_values = [func(var_value, int(i)) for i in keys]

        # elif m := re.search(bitwise3_pattern, map_body):
        #     ...

        return "".join([chr(v) for v in raw_values])

    @classmethod
    def fallback(cls, s: "Extractor") -> str:
        to_try = [cls.slice, cls.map, cls.from_charcode]
        for t in to_try:
            try:
                key = t(s)
                break
            except ValueError:
                continue

        else:
            raise ValueError("key not found =(")

        return key

    @classmethod
    def resolve(cls, flags: int, s: "Extractor") -> bytes:
        key = ""

        if flags & ResolverFlags.MAP:
            key = cls.map(s)

        if flags & ResolverFlags.SLICE:
            key = cls.slice(s)

        if flags & ResolverFlags.REVERSE:
            key = "".join(reversed(key))

        if flags & ResolverFlags.FROMCHARCODE:
            key = cls.from_charcode(s)

        if flags & ResolverFlags.FALLBACK:
            key = cls.fallback(s)

        return key.encode()


async def make_request(url: str, headers: dict, params: dict, func: Callable[[aiohttp.ClientResponse], Awaitable[T]]) -> T:
    async with aiohttp.ClientSession() as client:
        async with client.get(url, headers=headers, params=params) as resp:
            return await func(resp)


@overload
def _re(pattern: Patterns | str, string: str, *, l: Literal[True]) -> list[str]: ...
@overload
def _re(pattern: Patterns | str, string: str, *, l: Literal[False]) -> re.Match: ...


def _re(pattern: Patterns | str, string: str, *, l: bool) -> re.Match | list[str]:
    if l:
        v = re.findall(pattern, string)

    else:
        v = re.search(pattern, string)

    if not v:
        msg = f"{pattern.name} not found" if isinstance(pattern, Patterns) else f"{pattern} not found"
        raise ValueError(msg)

    return v


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


def generate_sequence(n: int) -> list[int]:
    res = [5, 8, 14, 11]
    if n <= 4:
        return res

    for i in range(2, n - 2):
        res.append(res[i] + i + 3 - (i % 2))

    return res


class Extractor:
    def __init__(self, embed_url: str) -> None:
        self.embed_url = embed_url

        self.script: str
        self.string_array: list[str]
        self.bitwise: dict[int, Callable]

    def _generate_bitwise_func(self, operation: str) -> Callable:
        operation = re.sub(r"[\w$]{2}", "args", operation)
        if any(i in operation for i in (">", "<")):
            v = operation.split()
            v[-1] = f"({v[-1]} & 31)"
            operation = " ".join(v)

        return lambda *args: eval(operation)

    def _get_bitwise_operations(self) -> dict[int, Callable]:
        functions = {}

        switchcase_section = _re(Patterns.BITWISE_SWITCHCASE, self.script, l=False).group(1)
        for num, operation in _re(Patterns.BITWISE_OPERATION, switchcase_section, l=True):
            functions[int(num)] = self._generate_bitwise_func(operation.split("=")[1])

        return functions

    def _get_array_slices(self) -> list[tuple[int, ...]]:
        pairs = tuple(map(lambda t: tuple(map(int, t)), _re(Patterns.SLICES, self.script, l=True)))
        order_map = {v: i for i, v in enumerate(generate_sequence(len(pairs)))}

        pairs = list(sorted(pairs, key=lambda t: order_map[t[0]]))
        return pairs

    def _shuffle_array(self, array: list[str]) -> list[str]:
        slices = self._get_array_slices()
        for _, array_idx, tail_idx in slices:
            array, tail = array[:array_idx], array[array_idx:]
            array = tail[:tail_idx] + array

        return array

    def _get(self, values) -> str:
        values = list(filter(None, values))

        if len(values) == 1 or not values[1].isdigit():
            if len(values) == 2:
                if any(i in values[1] for i in (">", "<")):
                    v = values[-1].split()
                    v[-1] = f"({v[-1]} & 31)"
                    values[-1] = " ".join(v)

                e = f"{values[0]}{values[1]}"
                i = eval(e)

            else:
                i = int(values[0])

            v = self.string_array[i]

        elif len(values) > 1:
            i1 = int(values[0])
            i2 = int(values[1])
            flag = int(values[2]) if len(values) == 3 else 0

            i = self.bitwise[flag](i1, i2)
            v = self.string_array[i]

        else:
            raise ValueError(f"can't get {values}")

        return v

    def _get_indexes(self) -> list[int]:
        indexes = []
        array_items = _re(Patterns.INDEX_ARRAY_CONTENT, self.script, l=True)[-1]

        for m in _re(Patterns.INDEX_ARRAY_ITEM, array_items, l=True):
            idx = m[0] or m[1] or m[2]

            if not idx.isdigit():
                idx = _re(Patterns.IDX, idx, l=False).group(1)

            indexes.append(int(idx))

        return indexes

    def _resolve_key(self) -> bytes:
        keygen_func = _re(Patterns.KEYGEN, self.script, l=False)
        keygen_body = keygen_func.group(1)

        functions = []
        print(keygen_body)

        for i in re.findall(Patterns.GET, keygen_body):
            functions.append(self._get(i))

        print(functions)
        flags = 0

        if "slice" in functions:
            flags |= ResolverFlags.SLICE

        elif "reverse" in functions:
            flags |= ResolverFlags.SLICE
            flags |= ResolverFlags.REVERSE

        elif "map" in functions:
            if "fromCharCode" in functions:
                flags |= ResolverFlags.FROMCHARCODE

            else:
                flags |= ResolverFlags.MAP

        else:
            flags |= ResolverFlags.FALLBACK

        key = Resolvers.resolve(flags, self) or b":P"
        return key

    async def _get_secret_key(self) -> bytes:
        strings = ""

        script_url = f"{base_url}/js/player/a/v2/pro/embed-1.min.js"
        script_version = int(time.time())
        self.script = await make_request(script_url, {}, {"v": script_version}, lambda i: i.text())

        xor_key = _re(Patterns.XOR_KEY, self.script, l=False).group(1)
        char_sequence = parse.unquote(_re(Patterns.STRING, self.script, l=False).group(1))
        delim = _re(Patterns.DELIMITER, self.script, l=False).group(1)

        for i in range(len(char_sequence)):
            a = ord(char_sequence[i])
            b = ord(xor_key[i % len(xor_key)])

            idx = a ^ b
            strings += chr(idx)

        string_array = strings.split(delim)
        self.string_array = self._shuffle_array(string_array)
        self.bitwise = self._get_bitwise_operations()

        key = self._resolve_key()
        return key

    async def extract(self) -> dict:
        headers = {
            "User-Agent": user_agent,
            "Referer": base_url,
            "Origin": base_url,
        }

        id = _re(Patterns.SOURCE_ID, self.embed_url, l=False).group(1)
        get_src_url = f"{base_url}/embed-2/v2/e-1/getSources"

        resp = await make_request(get_src_url, headers, {"id": id}, lambda i: i.json())

        if not resp["sources"]:
            raise ValueError("no sources found")

        key = await self._get_secret_key()
        print(key.decode())

        sources = json.loads(decrypt_sources(key, resp["sources"]))

        resp["sources"] = sources

        resp["intro"] = resp["intro"]["start"], resp["intro"]["end"]
        resp["outro"] = resp["outro"]["start"], resp["outro"]["end"]

        return resp


async def main():
    url = "https://megacloud.blog/embed-2/v2/e-1/K18vG6wteK42?k=1&autoPlay=1&oa=0&asi=1"
    a = Extractor(url)
    print(json.dumps(await a.extract(), indent=4))


asyncio.run(main())
