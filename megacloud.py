import base64
import hashlib
import json
import time
import subprocess
import os
import tempfile
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
    SPLIT = 1 << 4
    FALLBACK = 1 << 5


class Patterns(StrEnum):
    _FUNC = r"[\w$]{3}\.[\w$]{2}"
    _FUNC2 = r"[\w$]\.[\w$]{2}"
    _FUNC3 = r"[\w$]{3}\.[\w$]{3}"

    SOURCE_ID = r"embed-2/v2/e-1/([A-z0-9]+)\?"

    IDX = r'"(\d+)"'
    VAR = r';{}=\+?"?(\d+)"?;'

    XOR_KEY = r"\)\('(.+)'\)};"
    STRING = r"function [\w$]{2}\(\){return \"(.+?)\";}"
    DELIMITER = r"[\w$]{3}=\w\.[\w$]{2}\([\w$]{3},'(.)'\);"

    BITWISE_SWITCHCASE = r"\w\[\d+\]=\(function\([\w$]+\)[{\d\w$:\(\),= ]+;switch\([\w$]+\){([^}]+)}"
    BITWISE_OPERATION = r"case (\d+):([\w\[\]\-+|><^* =$]+);break;"

    SLICES = rf"case\s(\d{{1,2}}):{_FUNC2}\({_FUNC2}\(\),[\w$]{{3}},{_FUNC2}\({_FUNC2}\([\w$]{{3}},([\d\-]+),[\d\-]+\),[\d\-]+,([\d\-]+)\)\)"

    GET1_FUNC = rf'({_FUNC}\(\+?"?\d+"?(?: [|\-\+*><^]+ "?\d+"?)?\))'
    GET2_FUNC = rf'({_FUNC}\({_FUNC}\("?\d+"?,"?\d+"?\)\))'
    GET3_FUNC = rf'({_FUNC}\({_FUNC}\("?\d+"?,"?\d+"?,{_FUNC}\(\d\)\)\))'
    GET_FUNC = f"{GET1_FUNC}|{GET2_FUNC}|{GET3_FUNC}"

    _GET1_INDEX = r'+?"?(\d+)"?(?:( [|\-\+*><^]+ "?\d+"?))?'
    GET1 = rf"{_FUNC}\(\{_GET1_INDEX}\)"
    GET2 = rf'{_FUNC}\({_FUNC}\("?(\d+)"?,"?(\d+)"?\)\)'
    GET3 = rf'{_FUNC}\({_FUNC}\("?(\d+)"?,"?(\d+)"?,{_FUNC}\((\d)\)\)\)'
    GET = f"{GET1}|{GET2}|{GET3}"

    INDEX_ARRAY_CONTENT = r'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    INDEX_ARRAY_ITEM = rf'({_FUNC}\([\w",\(\)]+\))|({_FUNC}\("?\d+"?,"?\d+"?,{_FUNC}\(\d+\)\))|(\d+)'

    KEY_ARRAY_CONTENT = rf'\w=\[((?!arguments)[\w\d.$\(\)",+]+)\];'
    KEY_VAR = rf'var [\w$,]{{28,}};(?:{_FUNC}\(\+?"?\d+"?\);)?[\w$]+=([\w$.\(\)\+,"]+);'

    KEYGEN = r"var [\w$,]{28,};.+?\w=\(\)=>{(.+?)};"
    MAP = r"\((\w)=>{(.+?return.+?;)"

    PARSE_INT = r'\w+\({},\+?"16"?\)'
    BITWISE2 = rf"{_FUNC}\((\w),(\w\))"
    BITWISE3 = rf'{_FUNC}\("?(\d+)"?,"?(\d+)"?,{_FUNC}\((\d)\)\)'
    SET_DEF_FLAG = rf'{_FUNC}\(\+?"?(\d+)"?\)'

    GET_KEY = r"var [\w$,]{28,};(.+?)try"
    GET_KEY_FUNC = r"(\w)=\(\)=>{(.+?)};"


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

    @staticmethod
    def _prepare(to_execute: str, s: "Extractor") -> str:
        for f in _re(Patterns.GET_FUNC, to_execute, l=True):
            call = f[0]
            string = s._get(_re(Patterns.GET, call, l=False).groups())

            to_execute = to_execute.replace(call, f'"{string}"')

        to_execute = re.sub(rf"if\({Patterns._FUNC}\(\)\)|if\({Patterns._FUNC3}\(\)\)", "if(1)", to_execute)
        to_execute = re.sub(rf"{Patterns._FUNC}\(\);|{Patterns._FUNC3}\(\);", "", to_execute)

        get_key_func_name = _re(Patterns.GET_KEY_FUNC, to_execute, l=False).group(1)
        to_execute += f"console.log({get_key_func_name}());"

        return to_execute

    @classmethod
    def slice(cls, s: "Extractor") -> tuple[list, list]:
        key = cls._get_key(s)
        if key.endswith("="):
            key = base64.b64decode(key).decode()

        return list(key), list(range(0, len(key)))

    @classmethod
    def map(cls, s: "Extractor") -> tuple[list, list]:
        keys = cls._get_keys(s)
        try:
            indexes = s._get_indexes()
        except ValueError:
            indexes = []

        return keys, indexes

    @classmethod
    def from_charcode(cls, s: "Extractor", keys: list = [], indexes: list = []) -> tuple[list, list]:
        raw_values = []

        if indexes:
            try:
                map_ = _re(Patterns.MAP, s.script, l=False)
                map_arg = map_.group(1)
                map_body = map_.group(2)

            except ValueError:
                indexes = s._get_indexes()
                raw_values = [int(i) for i in indexes]

            else:
                if m := re.search(Patterns.BITWISE2, map_body):
                    flag = _re(Patterns.SET_DEF_FLAG, map_body, l=False).group(1)
                    func = s.bitwise[int(flag)]

                    var_name = m.group(1) if m.group(1) != map_arg else m.group(2)
                    var_value = _re(Patterns.VAR.format(var_name), s.script, l=False).group(1)

                    raw_values = [func(int(var_value), int(i)) for i in indexes]

        elif keys:
            map_ = _re(Patterns.MAP, s.script, l=False)
            map_arg = map_.group(1)
            map_body = map_.group(2)

            if re.search(Patterns.PARSE_INT.format(map_arg), map_body):
                raw_values = [int(k, 16) for k in keys]

            # elif m := re.search(bitwise3_pattern, map_body):
            #     ...

        return [chr(v) for v in raw_values], list(range(0, len(raw_values)))

    @classmethod
    def fallback(cls, s: "Extractor") -> tuple[list, list]:
        to_try = [cls.node_proc, cls.slice, cls.map, cls.from_charcode]

        for t in to_try:
            try:
                return t(s)
            except ValueError:
                continue

        else:
            raise ValueError("no key found =(")

    @classmethod
    def node_proc(cls, s: "Extractor") -> tuple[list, list]:
        to_execute = _re(Patterns.GET_KEY, s.script, l=False).group(1)
        to_execute = cls._prepare(to_execute, s)

        tmp = tempfile.mktemp()
        with open(tmp, "w") as f:
            f.write(to_execute)

        # i hate this way of doing things
        # might think of sum else later

        proc = subprocess.run(["node", tmp], capture_output=True, text=True)
        os.remove(tmp)
        if proc.returncode != 0:
            raise OSError(proc.stderr)

        key = proc.stdout.strip()
        return list(key), list(range(0, len(key)))

    @classmethod
    def resolve(cls, flags: int, s: "Extractor") -> bytes:
        key = ""
        keys = []
        indexes = []

        if flags & ResolverFlags.MAP:
            keys, indexes = cls.map(s)

        if flags & (ResolverFlags.SLICE | ResolverFlags.SPLIT):
            keys, indexes = cls.slice(s)

        if flags & ResolverFlags.FROMCHARCODE:
            keys, indexes = cls.from_charcode(s, keys, indexes)

        if flags & ResolverFlags.FALLBACK:
            keys, indexes = cls.fallback(s)

        key = "".join(keys[i] for i in indexes)

        if flags & ResolverFlags.REVERSE:
            key = "".join(reversed(key))

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

        functions: list[str] = []

        for i in re.findall(Patterns.GET, keygen_body):
            functions.append(self._get(i))

        flags = 0

        for f in functions:
            if f.upper() in ResolverFlags._member_names_:
                flags |= ResolverFlags[f.upper()]

        if not flags:
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
        sources = json.loads(decrypt_sources(key, resp["sources"]))

        resp["sources"] = sources

        resp["intro"] = resp["intro"]["start"], resp["intro"]["end"]
        resp["outro"] = resp["outro"]["start"], resp["outro"]["end"]

        return resp


async def main():
    url = "	https://megacloud.blog/embed-2/v2/e-1/4bhHN8KmRgir?k=1&autoPlay=1&oa=0&asi=1"
    a = Extractor(url)
    print(json.dumps(await a.extract(), indent=4))


asyncio.run(main())
